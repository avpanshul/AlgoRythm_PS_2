r"""Seeds the 9 baseline vendor source packs (Palo Alto, Cisco ASA, FortiGate,
pfSense, Suricata EVE, Windows Firewall, Squid, Zeek/Bro, AWS CloudTrail) plus
generic syslog/CEF/LEEF coverage, required by ULPF-combined-prompt.md Part C2.

Sample provenance (checked per-pack, 2026-09-25 -- no live device access was
available in this environment, so "real" here means "sourced from a real,
independently checkable public capture or vendor doc," not "captured from our
own production traffic"):

  - Cisco ASA:    REAL. From Elastic Beats' own Cisco ASA module test fixture
                  (github.com/elastic/beats, x-pack/filebeat/module/cisco/asa/test/sample.log).
  - Squid:        REAL log body (github gist, a genuine Filebeat Squid parsing
                  test case) wrapped in a syslog envelope for transport --
                  Squid ships this format via syslog in practice, but the
                  specific envelope (PRI/timestamp/hostname/pid) here is
                  reconstructed, not itself captured.
  - pfSense:      REAL log body (docs.netgate.com's own filterlog reference
                  example, field-for-field), same syslog-envelope caveat as Squid.
  - Suricata EVE: REAL. Verbatim example object from Suricata's own official
                  documentation (docs.suricata.io/en/latest/output/eve/eve-json-format.html).
  - FortiGate:    REAL fields, from Fortinet's own FortiOS documentation
                  (docs.fortinet.com sample-logs-by-log-type), though the
                  excerpt found was partial -- only the fields it actually
                  contains are mapped, nothing was invented to fill gaps.
  - Windows FW:   REAL field VALUES for a documented Event ID 5157 example
                  (ultimatewindowssecurity.com's own reference page); the XML
                  envelope around them follows the public Windows Event Schema
                  but was not itself captured from a real machine.
  - Palo Alto:    SYNTHETIC. No trustworthy real PAN-OS CSV sample could be
                  found -- every "real" line surfaced by search had hallmarks
                  of being an AI-generated example (implausibly complete,
                  identical content resurfacing across unrelated queries), so
                  it was rejected rather than passed off as real. This pack
                  stays a hand-written, format-accurate synthetic fixture
                  until a genuine sample is available.
  - Zeek/Bro:     REAL. Genuine Zeek/Bro IDS engine output from a user-supplied
                  dataset dump (a Team Cymru Malware Hash Registry match with a
                  matching VirusTotal link) -- see
                  backend/datasets/real/build_zeek_corpus.py for full detail.
  - AWS CloudTrail: REAL. From invictus-ir/aws_dataset (MIT) -- a genuine
                  CloudTrail export from a Stratus Red Team attack simulation
                  against a real AWS account (real IAM ARN, real request ID,
                  real x-amz-id-2 signature). See
                  backend/datasets/real/build_cloudtrail_corpus.py.

Every pack is registered with coverage_status="fixture" regardless of the
above -- none of this is "verified" (seen on ULPF's own live traffic), which
is a higher bar than "sourced from a real capture." publish_parser() (see
app/api/v1/parsers_api.py) will refuse to publish any pack whose sample
doesn't actually parse and normalize -- so "published" means "passes its own
fixture test," never "seen on real traffic."

Usage: POSTGRES_PASSWORD=x python scripts/seed_vendor_packs.py
       (or run against the SQLite demo DB: import this after run_local_demo's
       engine patch, or just run scripts/run_local_demo.py first then this.)
"""
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.all import Parser
from app.api.v1.parsers_api import _run_parser_fixture_test


PACKS = [
    {
        "id": "paloalto_traffic_csv",
        "name": "Palo Alto Networks - Traffic Log (CSV) [SYNTHETIC -- see module docstring]",
        "vendor": "PaloAlto",
        "device_type": "firewall",
        "format_type": "CSV",
        # SYNTHETIC: simplified subset of the documented PAN-OS TRAFFIC CSV schema
        # (the full schema has 60+ positional columns; this keeps the fixture
        # readable while staying genuinely positional/comma-delimited like the
        # real export). No trustworthy real sample was found -- see docstring.
        "sample_log": "2026/09/24 10:00:00,TRAFFIC,end,2026/09/24 10:00:00,192.168.1.10,203.0.113.45,Allow-Web,49231,443,tcp,allow,IDS-SSH-Brute",
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "field_4", "canonical_field": "source_ip"},
                {"raw_field": "field_5", "canonical_field": "dest_ip"},
                {"raw_field": "field_7", "canonical_field": "source_port"},
                {"raw_field": "field_8", "canonical_field": "dest_port"},
                {"raw_field": "field_9", "canonical_field": "network_protocol"},
                {"raw_field": "field_10", "canonical_field": "event_data.outcome"},
                {"raw_field": "field_6", "canonical_field": "event_data.action"},
                {"raw_field": "field_1", "canonical_field": "event_data.type"},
                {"raw_field": "field_11", "canonical_field": "message"},
            ],
            "static": {"device_vendor": "PaloAlto", "device_product": "PAN-OS", "event_data": {"category": "network"}},
        }, sort_keys=False),
    },
    {
        "id": "cisco_asa_syslog",
        "name": "Cisco ASA - Connection Built/Teardown (Syslog)",
        "vendor": "Cisco",
        "device_type": "firewall",
        "format_type": "Syslog",
        # REAL: from Elastic Beats' own Cisco ASA test fixture (see docstring).
        "sample_log": '<166>Apr 29 2013 12:59:50: %ASA-6-302016: Teardown UDP connection 89743275 for outside:192.0.2.222/53 to inside:10.123.1.35/52925 duration 1:23:45 bytes 140',
        "config_yaml": yaml.dump({
            # Free-text regex extraction (see app/parsers/mapping_engine.py) -- ASA
            # syslog embeds real fields in prose, not key=value, so this is the only
            # way to field-map it without a full ASA grammar parser.
            "field_mappings": [
                {"raw_field": "message", "canonical_field": "source_ip", "regex": r"outside:(\d{1,3}(?:\.\d{1,3}){3})"},
                {"raw_field": "message", "canonical_field": "dest_ip", "regex": r"inside:(\d{1,3}(?:\.\d{1,3}){3})"},
                {"raw_field": "message", "canonical_field": "dest_port", "regex": r"inside:[\d.]+/(\d+)"},
                {"raw_field": "message", "canonical_field": "event_data.action", "regex": r"%ASA-\d-\d+: (\w+)"},
                {"raw_field": "message", "canonical_field": "network_protocol", "regex": r"(TCP|UDP) connection"},
                {"raw_field": "message", "canonical_field": "message"},
            ],
            "static": {"device_vendor": "Cisco", "device_product": "ASA", "event_data": {"category": "network", "type": "connection"}},
        }, sort_keys=False),
    },
    {
        "id": "fortigate_traffic_kv",
        "name": "Fortinet FortiGate - Traffic Log (Key-Value, syslog-wrapped)",
        "vendor": "Fortinet",
        "device_type": "firewall",
        # REAL fields, from Fortinet's own FortiOS documentation. Two real bugs
        # fixed here, both found by actually ingesting the real sample rather
        # than assuming the pack worked:
        # 1. FortiOS's real wire format has a `<189>` syslog PRI prefix, but
        #    its body is `date=... time=...` key=value pairs, not a classic
        #    BSD "Mon DD HH:MM:SS" timestamp -- app/parsers/deterministic.py's
        #    parse_syslog() regex doesn't match that, so it fell into its own
        #    fallback branch (whole raw log to `message`), while this pack was
        #    registered as format_type "KeyValue" and so never got selected at
        #    all (format_detector.py correctly calls the raw string "Syslog"
        #    because of the `<189>` prefix). Fixed by declaring format_type
        #    "Syslog" and extracting each field via regex against `message`
        #    (same pattern pfsense_filterlog_syslog already uses for its own
        #    syslog-wrapped body).
        # 2. `type` was previously mis-mapped to event_data.action (it's the
        #    log *category*, e.g. "traffic", not an action) because the real
        #    `action=` field wasn't in the original short excerpt. A fuller
        #    real sample (docs.fortinet.com's FORWARD_TRAFFIC example,
        #    reproduced via napalm-logs) surfaced it. `crlevel` (FortiOS's own
        #    real Cyber Risk Level: low/medium/high/critical) and the real
        #    byte counters are now also captured rather than discarded.
        "format_type": "Syslog",
        "sample_log": '<189>date=2019-04-09 time=04:27:29 devname=fw01 devid=FG800D0123456789 logid=0000000013 type=traffic subtype=forward level=notice vd=root srcip=1.1.1.1 srcport=19982 srcintf="port1" dstip=10.10.10.10 dstport=179 dstintf="port3" action=timeout policyid=34 service="BGP" duration=25 sentbyte=300 rcvdbyte=0 crlevel=low',
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "message", "canonical_field": "source_ip", "regex": r"srcip=(\S+)"},
                {"raw_field": "message", "canonical_field": "dest_ip", "regex": r"dstip=(\S+)"},
                {"raw_field": "message", "canonical_field": "source_port", "regex": r"srcport=(\d+)"},
                {"raw_field": "message", "canonical_field": "dest_port", "regex": r"dstport=(\d+)"},
                {"raw_field": "message", "canonical_field": "event_data.action", "regex": r"\baction=(\S+)"},
                {"raw_field": "message", "canonical_field": "event_data.type", "regex": r"subtype=(\S+)"},
                {"raw_field": "message", "canonical_field": "event_data.severity", "regex": r"\blevel=(\S+)"},
                {"raw_field": "message", "canonical_field": "event_data.vendor_risk_level", "regex": r"crlevel=(\S+)"},
                {"raw_field": "message", "canonical_field": "event_data.bytes_out", "regex": r"sentbyte=(\d+)"},
                {"raw_field": "message", "canonical_field": "event_data.bytes_in", "regex": r"rcvdbyte=(\d+)"},
                {"raw_field": "message", "canonical_field": "message"},
            ],
            "static": {"device_vendor": "Fortinet", "device_product": "FortiGate", "event_data": {"category": "network"}},
        }, sort_keys=False),
    },
    {
        "id": "pfsense_filterlog_syslog",
        "name": "pfSense - Firewall Filter Log (Syslog-wrapped CSV)",
        "vendor": "pfSense",
        "device_type": "firewall",
        "format_type": "Syslog",
        # pfSense's filterlog is itself CSV, but it arrives wrapped in a syslog
        # message (the message body is the CSV row) -- so this is Syslog format
        # at detection time, with regex-based positional extraction on the message.
        # CSV body is REAL (docs.netgate.com's own reference example); the syslog
        # envelope around it is reconstructed, not itself captured -- see docstring.
        "sample_log": "<134>Sep 24 10:00:00 pfSense filterlog[12345]: 4,,,1000000103,pppoe0,match,block,in,4,0x0,,242,26160,0,none,6,tcp,44,89.248.165.17,125.229.96.130,44961,30129,0,S,3258086147,,1025,,mss",
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "message", "canonical_field": "event_data.action", "regex": r"filterlog\[\d+\]: \d+,,,\d+,\w+,\w+,(\w+),"},
                {"raw_field": "message", "canonical_field": "source_ip", "regex": r"(?:tcp|udp),\d+,(\d{1,3}(?:\.\d{1,3}){3})", "regex_group": 1},
                {"raw_field": "message", "canonical_field": "dest_ip", "regex": r"(?:tcp|udp),\d+,\d{1,3}(?:\.\d{1,3}){3},(\d{1,3}(?:\.\d{1,3}){3})"},
                {"raw_field": "message", "canonical_field": "network_protocol", "regex": r",(tcp|udp),\d+,\d{1,3}(?:\.\d{1,3}){3}"},
                {"raw_field": "message", "canonical_field": "message"},
            ],
            "static": {"device_vendor": "pfSense", "device_product": "filterlog", "event_data": {"category": "network", "type": "connection"}},
        }, sort_keys=False),
    },
    {
        "id": "nginx_plus_kv",
        "name": "nginx plus - Access Log (Key-Value)",
        "vendor": "nginx",
        "device_type": "web_server",
        "format_type": "KeyValue",
        # REAL field, from a real captured nginx access log (Splunk's public
        # attack_data research repo, github.com/splunk/attack_data,
        # datasets/attack_techniques/T1567/web_upload_nginx/) -- a real
        # ~1GB single-request upload to a WordPress REST endpoint, the
        # documented technique this sample exists to illustrate
        # (T1567, Exfiltration Over Web Service). `bytes_out` is mapped to
        # event_data.bytes_out so app/core/processing.py's real
        # large-single-transfer risk signal can see it -- no field invented.
        "sample_log": 'site="www.example.com" server="www.example.com" dest_port="443" dest_ip="192.0.2.1" src="198.51.100.1" src_ip="198.51.100.1" user="-" time_local="22/Feb/2024:13:00:00 -0500" protocol="HTTP/1.1" status="200" bytes_out="1073741000" bytes_in="234" http_referer="-" http_user_agent="python-requests/2.25.1" uri_path="/wp-json/bricks/v1/render_element" http_method="POST"',
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "src_ip", "canonical_field": "source_ip"},
                {"raw_field": "dest_ip", "canonical_field": "dest_ip"},
                {"raw_field": "dest_port", "canonical_field": "dest_port"},
                {"raw_field": "http_method", "canonical_field": "event_data.action"},
                {"raw_field": "status", "canonical_field": "event_data.outcome"},
                {"raw_field": "bytes_out", "canonical_field": "event_data.bytes_out"},
                {"raw_field": "bytes_in", "canonical_field": "event_data.bytes_in"},
                {"raw_field": "uri_path", "canonical_field": "message"},
            ],
            "static": {"device_vendor": "nginx", "device_product": "nginx plus", "event_data": {"category": "web"}},
        }, sort_keys=False),
    },
    {
        "id": "windows_ntlm_8004_xml",
        "name": "Windows NTLM Authentication (Event ID 8004, raw namespaced XML)",
        "vendor": "Microsoft",
        "device_type": "domain_controller",
        "format_type": "XML",
        # REAL fields, from github.com/splunk/attack_data's real
        # datasets/attack_techniques/T1110.003/ntlm_bruteforce sample (a real
        # captured Windows Security-Netlogon/NTLM operational log from a real
        # attack-simulation lab run, not fabricated). The generic deterministic
        # XML parser mis-mapped this real event badly (WorkstationName into
        # source_ip, the raw EventID into action, the Keywords bitmask into
        # outcome) because it wasn't built for this namespaced XML shape --
        # found by actually ingesting a real sample and reading the result,
        # not assumed. Regex against the raw text (`message`, which
        # app/core/processing.py's normalize_with_source_pack now always
        # makes available regardless of parsed format) is more reliable here
        # than threading through the deeply-nested, namespace-prefixed parsed
        # dict keys.
        "sample_log": "<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System><Provider Name='Microsoft-Windows-Security-Netlogon' Guid='{E5BA83F6-07D0-46B1-8BC7-7E669A1D31DC}'/><EventID>8004</EventID><Version>0</Version><Level>4</Level><Task>2</Task><Opcode>0</Opcode><Keywords>0x8000000000000000</Keywords><TimeCreated SystemTime='2024-01-18T05:04:59.727635000Z'/><EventRecordID>2728229667</EventRecordID><Correlation/><Execution ProcessID='812' ThreadID='3684'/><Channel>Microsoft-Windows-NTLM/Operational</Channel><Computer>attack_dc.attack_range.lan</Computer><Security UserID='S-1-5-18'/></System><EventData><Data Name='SChannelName'>VICTIM_PC</Data><Data Name='UserName'>backup</Data><Data Name='DomainName'>NULL</Data><Data Name='WorkstationName'>WIN-SHKRDLDI338</Data><Data Name='SChannelType'>2</Data></EventData></Event>",
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "message", "canonical_field": "user_name", "regex": r"<Data Name='UserName'>([^<]*)</Data>"},
                {"raw_field": "message", "canonical_field": "event_data.target_workstation", "regex": r"<Data Name='WorkstationName'>([^<]*)</Data>"},
                {"raw_field": "message", "canonical_field": "event_data.target_domain", "regex": r"<Data Name='DomainName'>([^<]*)</Data>"},
                {"raw_field": "message", "canonical_field": "device_product", "regex": r"<Channel>([^<]*)</Channel>"},
                {"raw_field": "message", "canonical_field": "message", "regex": r"<Computer>([^<]*)</Computer>"},
            ],
            "static": {
                "device_vendor": "Microsoft",
                "event_data": {"category": "authentication", "type": "ntlm", "action": "ntlm_authentication_attempt", "severity": "info"},
            },
        }, sort_keys=False),
    },
    {
        "id": "suricata_eve_json",
        "name": "Suricata - EVE JSON (Alert)",
        "vendor": "Suricata",
        "device_type": "ids",
        "format_type": "JSON",
        # REAL: verbatim from Suricata's own official docs (see docstring).
        "sample_log": '{"timestamp":"2023-09-18T06:13:41.532140+0000","flow_id":1676750115612680,"pcap_cnt":130,"event_type":"alert","src_ip":"142.11.240.191","src_port":35361,"dest_ip":"192.168.100.237","dest_port":49175,"proto":"TCP","pkt_src":"wire/pcap","tx_id":1,"alert":{"action":"allowed","gid":1,"signature_id":2045001,"rev":1,"signature":"ET ATTACK_RESPONSE Win32/LeftHook Stealer Browser Extension Config Inbound","category":"A Network Trojan was detected","severity":1},"app_proto":"http"}',
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "src_ip", "canonical_field": "source_ip"},
                {"raw_field": "dest_ip", "canonical_field": "dest_ip"},
                {"raw_field": "src_port", "canonical_field": "source_port"},
                {"raw_field": "dest_port", "canonical_field": "dest_port"},
                {"raw_field": "proto", "canonical_field": "network_protocol"},
                {"raw_field": "alert.signature", "canonical_field": "message"},
                {"raw_field": "alert.category", "canonical_field": "event_data.action"},
                {"raw_field": "event_type", "canonical_field": "event_data.type"},
            ],
            "static": {"device_vendor": "Suricata", "device_product": "EVE", "event_data": {"category": "network", "severity": "high"}},
        }, sort_keys=False),
    },
    {
        "id": "windows_firewall_xml",
        "name": "Windows Defender Firewall (Event Log XML)",
        "vendor": "Microsoft",
        "device_type": "host_firewall",
        "format_type": "XML",
        # Field VALUES are REAL -- ultimatewindowssecurity.com's own documented
        # example for Event ID 5157 (process, addresses, ports, protocol, layer).
        # The XML envelope follows the public Windows Event Schema but wasn't
        # itself captured from a real machine -- see docstring.
        "sample_log": (
            '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
            '<System><Provider Name="Microsoft-Windows-Windows Firewall With Advanced Security"/>'
            '<EventID>5157</EventID><Level>0</Level><Task>12810</Task>'
            '<TimeCreated SystemTime="2026-09-24T10:00:00.000000000Z"/>'
            '<Computer>WORKSTATION.contoso.local</Computer></System>'
            '<EventData><Data Name="ProcessID">1224</Data>'
            '<Data Name="Application">\\device\\harddiskvolume1\\windows\\system32\\svchost.exe</Data>'
            '<Data Name="Direction">%%14592</Data>'
            '<Data Name="SourceAddress">224.0.0.252</Data><Data Name="SourcePort">5355</Data>'
            '<Data Name="DestAddress">10.45.45.102</Data><Data Name="DestPort">56927</Data>'
            '<Data Name="Protocol">17</Data>'
            '<Data Name="FilterRTID">0</Data><Data Name="LayerName">%%14611</Data>'
            '<Data Name="LayerRTID">44</Data></EventData></Event>'
        ),
        "config_yaml": yaml.dump({
            # XML source packs aren't wired to the field-mapping engine (see
            # normalize_parsed_data's XML branch, which uses generic key-substring
            # matching instead) -- registered here for the coverage matrix and
            # publish-gate fixture test; live normalization uses the deterministic
            # XML path, which already covers Windows Event Log XML.
            "static": {"device_vendor": "Microsoft", "device_product": "Windows Firewall"},
        }, sort_keys=False),
    },
    {
        "id": "squid_access_syslog",
        "name": "Squid Proxy - Access Log (Syslog-wrapped)",
        "vendor": "Squid",
        "device_type": "proxy",
        "format_type": "Syslog",
        # Log body is REAL (a genuine Filebeat Squid-parsing test case, see
        # docstring); the syslog envelope around it is reconstructed, not
        # itself captured -- Squid does ship this format via syslog in practice.
        "sample_log": "<134>Sep 24 10:00:00 proxy01 squid[999]: 1348870236.160 0 192.168.0.35 TCP_DENIED/403 3293 GET http://armdl.adobe.com/pub/adobe/acrobat/win/9.x/9.5.2/misc/AcrobatUpd952_all_incr.msp - NONE/- text/html",
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "message", "canonical_field": "source_ip", "regex": r"squid\[\d+\]: [\d.]+ \d+ (\d{1,3}(?:\.\d{1,3}){3})"},
                {"raw_field": "message", "canonical_field": "event_data.action", "regex": r"(TCP_\w+)/\d+"},
                {"raw_field": "message", "canonical_field": "message", "regex": r"(GET|POST|PUT|DELETE) (\S+)", "regex_group": 2},
            ],
            "static": {"device_vendor": "Squid", "device_product": "proxy", "event_data": {"category": "network", "type": "http"}},
        }, sort_keys=False),
    },
    {
        "id": "zeek_notice_json",
        "name": "Zeek/Bro IDS - Notice Log (JSON)",
        "vendor": "Zeek",
        "device_type": "ids",
        "format_type": "JSON",
        # REAL: genuine Zeek/Bro engine output from a real capture -- a Team
        # Cymru Malware Hash Registry match against a real malware download URL,
        # with a matching VirusTotal detection link. See
        # backend/datasets/real/build_zeek_corpus.py for full provenance.
        # Zeek's own field names use literal dots (id.orig_h, not nested JSON) --
        # exercises the mapping engine's literal-dotted-key lookup.
        "sample_log": (
            '{"ts": "1325214418.652335", "uid": "CbCBU72DAp9fRO7Txl", '
            '"id.orig_h": "192.168.81.10", "id.orig_p": "1032", '
            '"id.resp_h": "79.137.237.80", "id.resp_p": "80", '
            '"note": "TeamCymruMalwareHashRegistry::Match", '
            '"msg": "Malware Hash Registry Detection rate: 71%  Last seen: 2014-03-08 00:33:38", '
            '"proto": "tcp", "actions": "Notice::ACTION_LOG", "zeek_log_type": "notice"}'
        ),
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "id.orig_h", "canonical_field": "source_ip"},
                {"raw_field": "id.resp_h", "canonical_field": "dest_ip"},
                {"raw_field": "id.orig_p", "canonical_field": "source_port"},
                {"raw_field": "id.resp_p", "canonical_field": "dest_port"},
                {"raw_field": "proto", "canonical_field": "network_protocol"},
                {"raw_field": "note", "canonical_field": "event_data.action"},
                {"raw_field": "msg", "canonical_field": "message"},
                {"raw_field": "zeek_log_type", "canonical_field": "event_data.type"},
            ],
            "static": {"device_vendor": "Zeek", "device_product": "NIDS", "event_data": {"category": "network", "severity": "high"}},
        }, sort_keys=False),
    },
    {
        "id": "aws_cloudtrail_json",
        "name": "AWS CloudTrail - Management Event (JSON)",
        "vendor": "AWS",
        "device_type": "cloud_audit",
        "format_type": "JSON",
        # REAL: from invictus-ir/aws_dataset (MIT), a genuine CloudTrail export
        # from an attack simulation against a real AWS account -- real IAM ARN,
        # real request ID, real x-amz-id-2 signature. See
        # backend/datasets/real/build_cloudtrail_corpus.py for full provenance.
        "sample_log": (
            '{"eventVersion": "1.08", "userIdentity": {"type": "IAMUser", '
            '"arn": "arn:aws:iam::123837392027:user/benjamin", "userName": "benjamin"}, '
            '"eventTime": "2023-07-10T11:42:44Z", "eventSource": "s3.amazonaws.com", '
            '"eventName": "GetBucketPublicAccessBlock", "awsRegion": "us-east-1", '
            '"sourceIPAddress": "10.248.16.43", "errorCode": "NoSuchPublicAccessBlockConfiguration", '
            '"errorMessage": "The public access block configuration was not found", '
            '"requestID": "NDWT6HCWYNQAHGDJ", "eventID": "8ca35bec-bc01-4a58-beca-6f8a16907e98", '
            '"eventType": "AwsApiCall", "eventCategory": "Management"}'
        ),
        "config_yaml": yaml.dump({
            "field_mappings": [
                {"raw_field": "sourceIPAddress", "canonical_field": "source_ip"},
                {"raw_field": "userIdentity.userName", "canonical_field": "user_name"},
                {"raw_field": "eventName", "canonical_field": "event_data.action"},
                {"raw_field": "eventCategory", "canonical_field": "event_data.type"},
                {"raw_field": "eventSource", "canonical_field": "message"},
            ],
            "static": {"device_vendor": "AWS", "device_product": "CloudTrail", "event_data": {"category": "cloud_audit"}},
        }, sort_keys=False),
    },
]


def main():
    db = SessionLocal()
    results = []
    try:
        for pack in PACKS:
            existing = db.query(Parser).filter(Parser.id == pack["id"]).first()
            if existing:
                print(f"skip (already exists): {pack['id']}")
                continue

            config_json = yaml.safe_load(pack["config_yaml"])
            parser = Parser(
                id=pack["id"], name=pack["name"], vendor=pack["vendor"],
                device_type=pack["device_type"], format_type=pack["format_type"],
                version="1.0.0", config_yaml=pack["config_yaml"], config_json=config_json,
                sample_log=pack["sample_log"], status="draft", created_by="seed_vendor_packs",
            )
            db.add(parser)
            db.commit()
            db.refresh(parser)

            fixture_result = _run_parser_fixture_test(parser, parser.sample_log)
            if fixture_result["status"] in ("success", "warning"):
                parser.status = "published"
                parser.coverage_status = "fixture"  # never "verified" -- no real traffic seen
                db.commit()
                results.append((pack["id"], "published", fixture_result["status"]))
            else:
                parser.coverage_status = "experimental"
                db.commit()
                results.append((pack["id"], "draft (fixture failed)", fixture_result.get("error")))
            print(f"{pack['id']}: {results[-1][1]} ({results[-1][2]})")
    finally:
        db.close()

    print("\n--- summary ---")
    for pack_id, outcome, detail in results:
        print(f"  {pack_id}: {outcome} -- {detail}")


if __name__ == "__main__":
    main()
