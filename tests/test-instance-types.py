import boto3

ec2_client = boto3.client("ec2", region_name="us-east-1")

validated_instances = [
    "p4d.24xlarge",
    "g4dn.2xlarge",
    "g4dn.8xlarge",
    "g4dn.16xlarge",
]

# List of instance types for which we create spot compute environments in AWS Batch.
spot_instance_types = [
    "p4d.24xlarge",
    "g4dn.2xlarge",
    "g4dn.8xlarge",
    "g4dn.16xlarge",
]


def filter_results(results):
    """
    Filter for x86_64 architecture and NVIDIA GPUs.
    """
    gpu_instances = [
        instance_type
        for instance_type in results["InstanceTypes"]
        if "GpuInfo" in instance_type
    ]
    NVIDIA_gpu_instances = [
        instance_type
        for instance_type in gpu_instances
        for gpu in instance_type["GpuInfo"]["Gpus"]
        if gpu["Manufacturer"] == "NVIDIA"
    ]
    x86_64_NVIDIA_gpu_instances = [
        {
            "InstanceType": instance_type["InstanceType"],
            "ProcessorInfo": instance_type["ProcessorInfo"],
            "VCpuInfo": instance_type["VCpuInfo"],
            "MemoryInfo": instance_type["MemoryInfo"],
            "GpuInfo": instance_type["GpuInfo"],
        }
        for instance_type in NVIDIA_gpu_instances
        if "x86_64" in instance_type["ProcessorInfo"]["SupportedArchitectures"]
    ]
    return x86_64_NVIDIA_gpu_instances


instance_types = {}
describe_args = {}
while True:
    results = ec2_client.describe_instance_types(**describe_args)

    # print only the instance types, result["InstanceType"]

    for result in filter_results(results):
        if result["InstanceType"] not in validated_instances:
            continue
        instance_types[result["InstanceType"]] = {
            "ProcessorInfo": result["ProcessorInfo"],
            "VCpuInfo": result["VCpuInfo"],
            "MemoryInfo": result["MemoryInfo"],
            "GpuInfo": result["GpuInfo"],
            "ProvisioningModel": {
                "EC2": "",  # EC2 = on-demand is the default provisioning model
            },
        }
        if result["InstanceType"] in spot_instance_types:
            instance_types[result["InstanceType"]]["ProvisioningModel"]["SPOT"] = ""
    if "NextToken" not in results:
        break
    describe_args["NextToken"] = results["NextToken"]

print(instance_types)


def filter_results(results):
    """
    Filter for x86_64 architecture and NVIDIA GPUs.
    """
    gpu_instances = [
        instance_type
        for instance_type in results["InstanceTypes"]
        if "GpuInfo" in instance_type
    ]
    NVIDIA_gpu_instances = [
        instance_type
        for instance_type in gpu_instances
        for gpu in instance_type["GpuInfo"]["Gpus"]
        if gpu["Manufacturer"] == "NVIDIA"
    ]
    print(NVIDIA_gpu_instances)
    x86_64_NVIDIA_gpu_instances = [
        {
            "InstanceType": instance_type["InstanceType"],
            "ProcessorInfo": instance_type["ProcessorInfo"],
            "VCpuInfo": instance_type["VCpuInfo"],
            "MemoryInfo": instance_type["MemoryInfo"],
            "GpuInfo": instance_type["GpuInfo"],
        }
        for instance_type in NVIDIA_gpu_instances
        if "x86_64" in instance_type["ProcessorInfo"]["SupportedArchitectures"]
    ]
    return x86_64_NVIDIA_gpu_instances
