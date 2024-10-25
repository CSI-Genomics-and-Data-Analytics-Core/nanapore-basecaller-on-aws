#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate ONT basecaller jobs for AWS Batch.
"""

import boto3

from basecaller_batch.basecaller_batch import (
    BasecallerBatch,
    terminate_all_jobs,
    deregister_all_job_definitions,
)

ssm_client = boto3.client("ssm")
aws_region_name = boto3.session.Session().region_name
account_id = boto3.client("sts").get_caller_identity().get("Account")

BASECALLER_DORADO_0_8_2 = f"{account_id}.dkr.ecr.{aws_region_name}.amazonaws.com/basecaller_guppy_latest_dorado0.8.2:latest"


dorado_no_modified_bases = (
    "dorado basecaller "
    "/usr/local/dorado/models/dna_r10.4.1_e8.2_400bps_hac@v3.5.2 "
    "${file_list}/ "
    "--verbose | "
    "samtools view --threads 8 -O BAM -o /fsx/out/&job_id&/calls.bam"
)

dorado_modified_bases_5mCG = (
    "dorado basecaller "
    "/usr/local/dorado/models/dna_r10.4.1_e8.2_400bps_hac@v3.5.2 "
    "${file_list}/ "
    "--verbose "
    "--modified-bases 5mCG | "
    "samtools view --threads 8 -O BAM -o /fsx/out/&job_id&/calls.bam"
)

dorado_modified_bases_5mCG_5hmCG = (
    "dorado basecaller "
    "/usr/local/dorado/models/dna_r10.4.1_e8.2_400bps_hac@v4.0.0 "
    "${file_list}/ "
    "--verbose "
    "--modified-bases 5mCG_5hmCG | "
    "samtools view --threads 8 -O BAM -o /fsx/out/&job_id&/calls.bam"
)

dorado_test = (
    "dorado basecaller "
    "/usr/local/dorado/models/rna004_130bps_fast@v5.1.0 "
    "${file_list}/ "
    "--verbose | "
    "samtools view --threads 8 -O BAM -o /fsx/out/&job_id&/calls.bam"
)


def main():
    aws_batch_env = BasecallerBatch()
    # terminate_all_jobs()  # <-- run this command to delete all running batch jobs
    # deregister_all_job_definitions()  # <-- run this command to delete all job definitions

    compute = [
        {"instance_type": "g4dn.2xlarge", "provisioning_model": "EC2"},
    ]

    # create dorado jobs
    aws_batch_env.create_batch_jobs(compute, cmd=dorado_test, tags="dorado, test")
    # aws_batch_env.create_batch_jobs(compute, cmd=dorado_no_modified_bases, tags='dorado, no modified bases')
    # aws_batch_env.create_batch_jobs(compute, cmd=dorado_modified_bases_5mCG, tags='dorado, modified bases 5mCG')
    # aws_batch_env.create_batch_jobs(compute, cmd=dorado_modified_bases_5mCG_5hmCG, tags='dorado, modified bases 5mCG & 5hmCG')


if __name__ == "__main__":
    main()
