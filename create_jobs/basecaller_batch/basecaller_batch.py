#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

Library for running the basecaller of Oxford Nanopore Technologies in an AWS Batch
environment.

"""

import json
import uuid
from string import Template

import boto3


ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
batch_client = boto3.client("batch")
aws_region_name = boto3.session.Session().region_name
account_id = boto3.client("sts").get_caller_identity().get("Account")

# Path to a JSON file with all instance types deployed in AWS Batch
# compute environments. This file is generated dynamically during deployment
# of the environment.
SSM_PARAMETER_STORE_INSTANCE_TYPES = "/ONT-basecaller/aws-batch-instance-types"
BASECALLER_DORADO_0_8_2 = f"{account_id}.dkr.ecr.{aws_region_name}.amazonaws.com/basecaller_guppy_latest_dorado0.8.2:latest"
BASECALLER_DOCKER_IMAGE = BASECALLER_DORADO_0_8_2

CONTAINER_SHORT_NAME = {
    BASECALLER_DORADO_0_8_2: "guppy-dorado0-8-2",
}

CONTAINER_PROPERTIES_TEMPLATE = {
    "image": "",
    "resourceRequirements": [
        {"type": "VCPU", "value": ""},
        {"type": "GPU", "value": ""},
        {"type": "MEMORY", "value": ""},
    ],
    "volumes": [
        {"host": {"sourcePath": "/fsx"}, "name": "FSx-for-Lustre"},
        {"host": {"sourcePath": "/usr/local/bin"}, "name": "usr_local_bin"},
    ],
    "mountPoints": [
        {"containerPath": "/fsx", "sourceVolume": "FSx-for-Lustre"},
        {"containerPath": "/host/bin", "sourceVolume": "usr_local_bin"},
    ],
}


class BasecallerBatch:

    def __init__(self):
        self.instance_types = None
        self.validated_instances = [
            "g4dn.metal",
            "g4dn.xlarge",
            "g4dn.2xlarge",
            "g4dn.4xlarge",
            "g4dn.8xlarge",
            "g4dn.12xlarge",
        ]
        self.instance_types = get_aws_batch_instance_types()
        # self.job_definitions = get_job_definitions()
        # self.create_missing_job_definitions()

    # def create_missing_job_definitions(self):
    #     """
    #     Ensure that for each AWS Batch compute environment there is a job definition.
    #     """
    #     missing_job_definitions = self.get_missing_job_definition_names()
    #     self.create_job_definitions(missing_job_definitions, self.instance_types)

    # def get_missing_job_definition_names(self):
    #     """
    #     Get all existing AWS Batch job definitions that match to compute environments.
    #     """
    #     expected_job_definitions = {}
    #     for instance_type in self.instance_types.keys():
    #         if 'EC2' in self.instance_types[instance_type]['ProvisioningModel']:
    #             expected_job_definitions[(instance_type.replace('.', '-'))] = instance_type
    #         if 'SPOT' in self.instance_types[instance_type]['ProvisioningModel']:
    #             expected_job_definitions[instance_type.replace('.', '-') + '-spot'] = instance_type
    #     missing_job_definitions = [
    #         {
    #             'job_definition_name': job_definition_name,
    #             'instance_type': expected_job_definitions[job_definition_name]
    #         }
    #         for job_definition_name in expected_job_definitions.keys()
    #         if job_definition_name not in self.job_definitions.keys()
    #     ]
    #     return missing_job_definitions

    # def create_job_definitions(self, job_definitions, instance_types):
    #     # instance_types = self.instance_types if instance_types is None else instance_types
    #     for job_definition in job_definitions:
    #         vcpus = instance_types[job_definition['instance_type']]['VCpuInfo']['DefaultVCpus']
    #         gpus = sum([gpu['Count'] for gpu in instance_types[job_definition['instance_type']]['GpuInfo']['Gpus']])
    #         memory = int(
    #             instance_types[job_definition['instance_type']]['MemoryInfo'][
    #                 'SizeInMiB'] * 0.9)  # reserve max. 90% of memory for tasks
    #         container_properties = CONTAINER_PROPERTIES_TEMPLATE
    #         container_properties['image'] = BASECALLER_DOCKER_IMAGE
    #         container_properties['resourceRequirements'][0]['value'] = str(vcpus)
    #         container_properties['resourceRequirements'][1]['value'] = str(gpus)
    #         container_properties['resourceRequirements'][2]['value'] = str(memory)
    #         batch_job_definition = batch_client.register_job_definition(
    #             jobDefinitionName=job_definition['job_definition_name'],
    #             type='container',
    #             parameters={
    #                 'tags': ''
    #             },
    #             containerProperties=container_properties,
    #         )
    #         self.job_definitions[job_definition['job_definition_name']] = batch_job_definition

    def create_batch_jobs(
        self,
        compute: list,
        container: str = BASECALLER_DOCKER_IMAGE,
        cmd: str = "",
        tags: str = "",
    ):
        params_templ = Template(cmd)
        for item in compute:  # aws_batch_env.validated_instances:
            max_vcpus = self.instance_types[item["instance_type"]]["VCpuInfo"][
                "DefaultVCpus"
            ]
            max_gpus = sum(
                [
                    gpu["Count"]
                    for gpu in self.instance_types[item["instance_type"]]["GpuInfo"][
                        "Gpus"
                    ]
                ]
            )
            max_memory = int(
                self.instance_types[item["instance_type"]]["MemoryInfo"]["SizeInMiB"]
                * 0.9
            )
            file_lists = ["/fsx/input/ont_1_file_8_0.lst"]  # 1 job per GPU
            # Unique identifier that allows to track which AWS batch jobs belong to the same data set
            data_set_id = str(uuid.uuid4())
            print("Generating AWS Batch jobs ...")
            for file_list in file_lists:
                params = params_templ.substitute(
                    file_list=file_list,
                    num_base_mod_threads=(
                        max_vcpus // max_gpus if (max_vcpus // max_gpus) <= 48 else 48
                    ),
                )
                job_id = self.submit_basecaller_job(
                    instance_type=item["instance_type"],
                    provisioning_model=item["provisioning_model"],
                    container=container,
                    basecaller_params=params,
                    gpus=1,
                    vcpus=max_vcpus // max_gpus,
                    memory=max_memory // max_gpus,
                    tags=[tags],
                    data_set_id=data_set_id,
                )
                print(
                    f'instance type: {item["instance_type"]}, tags: {tags}, file list: {file_list}, job ID: {job_id}'
                )
            print("Done. Check the status of the jobs in the AWS Batch console.")

    def submit_basecaller_job(
        self,
        instance_type="",
        provisioning_model="EC2",
        container=BASECALLER_DOCKER_IMAGE,
        basecaller_params="",
        **kwargs,
    ):
        job_queue = self.instance_types[instance_type]["ProvisioningModel"][
            provisioning_model
        ]
        job_definition_arn = self.get_job_definition_arn(
            instance_type, provisioning_model, container
        )
        container_overrides = self.make_container_overrides(basecaller_params, **kwargs)
        job = batch_client.submit_job(
            jobName=job_queue,
            jobQueue=job_queue,
            jobDefinition=job_definition_arn,
            containerOverrides=container_overrides,
            retryStrategy={"attempts": 10},
        )
        return job["jobId"]

    def get_job_definition_arn(self, instance_type, provisioning_model, container):
        """
        Get job definition ARN for given job queue, instance type and container. If job definition doesn't
        exist, create one.

        :return: job definition ARN
        """
        job_definition_name = f'{instance_type.replace(".", "-")}-{provisioning_model}-{CONTAINER_SHORT_NAME[container]}'
        job_definition = get_job_definition(job_definition_name)
        if job_definition:
            job_definition_arn = job_definition["jobDefinitionArn"]
        else:
            job_definition = self.create_job_definition(
                job_definition_name, instance_type=instance_type, container=container
            )
            job_definition_arn = job_definition["jobDefinitionArn"]
        return job_definition_arn

    def create_job_definition(
        self, job_definition_name, instance_type="", container=BASECALLER_DOCKER_IMAGE
    ):
        """
        Create job definition for given job definition name.

        :return: job definition details
        """
        vcpus = self.instance_types[instance_type]["VCpuInfo"]["DefaultVCpus"]
        gpus = sum(
            [
                gpu["Count"]
                for gpu in self.instance_types[instance_type]["GpuInfo"]["Gpus"]
            ]
        )
        memory = int(
            self.instance_types[instance_type]["MemoryInfo"]["SizeInMiB"] * 0.9
        )  # reserve max. 90% of memory for tasks
        container_properties = CONTAINER_PROPERTIES_TEMPLATE
        container_properties["image"] = container
        container_properties["resourceRequirements"][0]["value"] = str(vcpus)
        container_properties["resourceRequirements"][1]["value"] = str(gpus)
        container_properties["resourceRequirements"][2]["value"] = str(memory)
        job_definition = batch_client.register_job_definition(
            jobDefinitionName=job_definition_name,
            type="container",
            # parameters={'tags': ''},
            containerProperties=container_properties,
            tags={"application": "ONT Basecaller"},
        )
        return job_definition

    def make_container_overrides(self, basecaller_params="", **kwargs):
        env_vars = [
            {"name": "REGION", "value": aws_region_name},
        ]
        container_overrides = {"command": [basecaller_params]}
        if len(kwargs.keys()) > 0:
            container_overrides["resourceRequirements"] = []
            if "vcpus" in kwargs.keys():
                container_overrides["resourceRequirements"].append(
                    {"type": "VCPU", "value": str(kwargs["vcpus"])}
                )
            if "gpus" in kwargs.keys():
                container_overrides["resourceRequirements"].append(
                    {"type": "GPU", "value": str(kwargs["gpus"])}
                )
            if "memory" in kwargs.keys():
                container_overrides["resourceRequirements"].append(
                    {"type": "MEMORY", "value": str(kwargs["memory"])}
                )
            if "tags" in kwargs.keys():
                env_vars.append({"name": "TAGS", "value": ",".join(kwargs["tags"])})
            if "data_set_id" in kwargs.keys():
                env_vars.append({"name": "DATA_SET_ID", "value": kwargs["data_set_id"]})
        container_overrides["environment"] = env_vars
        return container_overrides


def get_aws_batch_instance_types():
    """
    Read list of AWS Batch compute environments. The list is stored as JSON file
    on S3. The list is generated during the CDK deployment of the AWS Batch environment.
    """
    param = ssm_client.get_parameter(Name=SSM_PARAMETER_STORE_INSTANCE_TYPES)
    file_obj = s3_client.get_object(
        Bucket=param["Parameter"]["Value"].split("/")[2],
        Key=param["Parameter"]["Value"].split("/")[3],
    )
    instance_types = json.loads(file_obj["Body"].read().decode("utf-8"))
    return instance_types


# def get_job_definitions():
#     job_definitions = {
#         job_definition['jobDefinitionName']: job_definition
#         for job_definition in batch_client.describe_job_definitions(status='ACTIVE')['jobDefinitions']
#     }
#     return job_definitions


def get_job_definition(job_definition_name):
    """
    Get job definition details for given job definition name.

    :return: job definition details
    """
    job_definitions = {
        job_definition["jobDefinitionName"]: job_definition
        for job_definition in batch_client.describe_job_definitions(status="ACTIVE")[
            "jobDefinitions"
        ]
    }
    if job_definition_name in job_definitions.keys():
        return job_definitions[job_definition_name]
    return None


def terminate_all_jobs():
    job_queues = batch_client.describe_job_queues()
    for job_queue in job_queues["jobQueues"]:
        for job_status in ["SUBMITTED", "PENDING", "RUNNABLE", "STARTING", "RUNNING"]:
            jobs = batch_client.list_jobs(
                jobQueue=job_queue["jobQueueName"],
                jobStatus=job_status,
            )
            for job in jobs["jobSummaryList"]:
                print(
                    f'terminating job: {job["jobId"]} in queue: {job_queue["jobQueueName"]}'
                )
                batch_client.terminate_job(
                    jobId=job["jobId"], reason="Cancelled by basecaller perf-bench"
                )


def deregister_all_job_definitions():
    """
    Deregister all job definitions. Call this function if there are issues with the job definitions.
    """
    job_definition_details = batch_client.describe_job_definitions(status="ACTIVE")
    for item in job_definition_details["jobDefinitions"]:
        print(f'Deleting job definition "{item["jobDefinitionName"]}" ...')
        batch_client.deregister_job_definition(jobDefinition=item["jobDefinitionArn"])
