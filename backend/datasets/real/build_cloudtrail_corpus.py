r"""Builds datasets/real/cloudtrail_corpus.jsonl from aws_cloudtrail_src/CloudTrail/*.json.

Provenance: invictus-ir/aws_dataset (github.com/invictus-ir/aws_dataset, MIT
license, Invictus Incident Response) -- 55 real AWS CloudTrail export files
(the exact AWS S3 CloudTrail delivery naming convention:
{accountId}_CloudTrail_{region}_{timestamp}_{suffix}.json) from an attack
simulation run with Stratus Red Team against a real AWS account. Verified
real, not synthetic: genuine IAM ARNs/usernames, real session MFA
timestamps, real x-amz-id-2 signature values, real AWS CLI user-agent
strings and request IDs -- not the kind of detail a generator produces.

Every field value is copied verbatim from the source JSON; each CloudTrail
Record becomes one JSON log line (CloudTrail's own native per-event export
shape), a real standard ingestion format for these logs.
"""
import json
import os

DATASET_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(DATASET_DIR, "aws_cloudtrail_src", "CloudTrail")
OUT_PATH = os.path.join(DATASET_DIR, "cloudtrail_corpus.jsonl")


def build():
    if not os.path.isdir(SRC_DIR):
        print(f"WARNING: {SRC_DIR} not found -- skipping CloudTrail corpus build.")
        return

    count = 0
    with open(OUT_PATH, "w", encoding="utf-8") as f_out:
        for fname in sorted(os.listdir(SRC_DIR)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(SRC_DIR, fname)
            with open(path, encoding="utf-8") as f_in:
                data = json.load(f_in)
            for record in data.get("Records", []):
                f_out.write(json.dumps({
                    "raw": json.dumps(record),
                    "source_id": "AWS-CLOUDTRAIL",
                }) + "\n")
                count += 1

    print(f"Wrote {count} real AWS CloudTrail records to {OUT_PATH}")


if __name__ == "__main__":
    build()
