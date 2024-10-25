# Introduction

This project sets up an environment for running [Oxford Nanopore Technologies](https://nanoporetech.com)’ basecallers, Guppy and Dorado, both of which rely heavily on GPUs.

We referenced [Benchmarking the Oxford Nanopore Technologies basecallers on AWS](https://aws.amazon.com/blogs/hpc/benchmarking-the-oxford-nanopore-technologies-basecallers-on-aws/) to select optimal AWS instance types for basecalling.

The initial CDK codebase is adapted from the [AWS basecaller-performance-benchmarking](https://github.com/aws-samples/basecaller-performance-benchmarking).

## Preparing the AWS account for deployment

This project automates the deployment of a basecaller environment using AWS CDK v2 for Python.

Tested in the **ap-southeast-1 (Singapore)** region, all instructions assume deployment in this region.

You’ll need to copy the NVIDIA CUDA base container from the public Docker repository to your private ECR repository. This container is essential for building the Guppy and Dorado containers.

Ensure your AWS credentials are set for the ap-southeast-1 region before running the commands.

```shell
cuda_container="nvidia/cuda:12.6.2-runtime-ubuntu22.04"
aws ecr create-repository --repository-name 'nvidia/cuda' --region ap-southeast-1
docker login
docker pull "$cuda_container"
aws_account_id=$(aws sts get-caller-identity --query 'Account' --output text)
docker tag "$cuda_container" "$aws_account_id.dkr.ecr.ap-southeast-1.amazonaws.com/$cuda_container"
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin "$aws_account_id.dkr.ecr.ap-southeast-1.amazonaws.com"
docker push "$aws_account_id.dkr.ecr.ap-southeast-1.amazonaws.com/$cuda_container"
```

## Deploying the project

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project. The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory. To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

Bootstrap the CDK environment. If you work with CDK regularly, you may have done this earlier.

```shell
npm install -g aws-cdk
cdk bootstrap
```

Run the following command to deploy the project.

```shell
cdk deploy --all
```

The project consists of multiple stacks. If you don't wish to manually confirm the deployment of each stack and the
security settings, you can run deployment with the following parameters: `--require-approval never` saves you from
confirming the security settings and `--no-prompts` removes the manual confirmation before deployment of each stack.

```shell
cdk deploy --all --require-approval never --no-prompts
```

## Validating deployment completion

After the CDK deployment of the infrastructure, a few automated steps are triggered. A base AMI image and a docker
container with the guppy and dorado tools are being build. The test data is being downloaded. The instructions
below help to check when these steps have been completed.

1. **CDK deployment:** The CDK deployment takes around 35 minutes. Once completed, CDK will display the following message on the command line.

```shell
ONT-Basecaller: deploying... [1/2]
ONT-Basecaller: creating CloudFormation changeset...

 ✅  ONT-Basecaller

✨  Deployment time: 1028.09s

Outputs:

<details removed for brevity>

✨  Total time: 1047.02s
```

2. **Base AMI image and docker container builds:** The base AMI image and docker container builds complete around 25 minutes
   after the CDK deployment has completed. To check the status, navigate to the [EC2 Image Builder console](https://ap-southeast-1.console.aws.amazon.com/imagebuilder/home?region=ap-southeast-1#/viewPipelines).
   Select the `ONT base AMI pipeline`. In the _Output images_ section you should see an image version with _Image status_ "Available":

Select the `ONT basecaller container pipeline` and check the _Output images_ section for an image version with
_Image status_ "Available":

3. **Test data download:** Downloading and converting the test data from FAST5 to POD5 format takes around 7.5 hours.

CDK deploys an EC2 instance (shown as "downloader" in the architecture diagram above) that
automatically downloads the [CliveOME 5mC dataset](https://labs.epi2me.io/cliveome_5mc_cfdna_celldna/)
data set as test data from an S3 bucket maintained by Oxford Nanopore. The data set has total size of 745 GiB.
After the download, the downloader instance will trigger the deletion of the downloader CDK stack. This is done to avoid
cost from an idle EC2 instance.

To check progress on the download open the [CloudWatch Logs console](https://ap-southeast-1.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-1#logsV2:log-groups/log-group/$252Faws$252FONTBasecaller$252Fdownloader)
and check the `/aws/ONTBasecaller/downloader` log group. The download is complete when you see the following lines at the
end of the log:

```
----- check download and conversion results -----
584 FAST5 files downloaded and converted to 584 POD5 files.
OK: Download and conversion successful.
----- delete downloader CloudFormation stack -----
-----
----- end UserData script -----
```

## Running the job

To start the job run the following command:

```shell
. ./.venv/bin/activate
python ./create_jobs/create_jobs.py
```

This command runs a Python script that will submit a number of AWS Batch jobs to be run on EC2
instances. The test data set is split across the number of GPUs and one AWS Batch job per GPU is generated. Jobs are
generated for running the `dorado` and the `guppy` basecallers. When executed successfully, you will see a
number of job IDs reported back:

To run on multiple EC2 instance types and different sets of `dorado` and `guppy` configurations, please adjust `./create_jobs/create_jobs.py`
to your requirements.

## Monitoring the execution of the running job

The jobs are tasks that, depending on the selected instance type, can run between 30 minutes and
several hours. The following steps provide guidance for how to check jobs have been submitted successfully and are
running.

1. **check submitted jobs are visible in AWS Batch:** after starting the jobs as described above, navigate to
   the [AWS Batch console](https://ap-southeast-1.console.aws.amazon.com/batch/home?region=ap-southeast-1). Scroll down to job queue
   "g4dn-xlarge". Immediately after submitting the jobs you will see the jobs with status "RUNNABLE".

2. **check EC2 instances are started:** once jobs have arrived, AWS Batch will automatically start the EC2 instances
   required to run the job. Navigate to the [EC2 Auto Scaling Groups console](https://ap-southeast-1.console.aws.amazon.com/ec2/home?region=ap-southeast-1#AutoScalingGroups:).
   Select the Auto Scaling group (ASG) that contains the job-queue name (e.g. \*g4dn-xlarge\*). In column "Instances" you
   should see that one or more instances have been launched.


Please note, if you are submitting jobs for EC2 instance types that are in high demand, you may see the following
message under the "Activity" tab of the ASG:

_"Could not launch On-Demand Instances. InsufficientInstanceCapacity - We currently do not have sufficient p3dn.24xlarge capacity in the Availability Zone you requested (ap-southeast-1c). Our system will be working on provisioning additional capacity."_

AWS Batch will automatically retry in the background to launch the required instance type and execute the job once
instances become available.

3. **check AWS Batch job enters "RUNNING" state:** Navigate to the [AWS Batch jobs console](https://ap-southeast-1.console.aws.amazon.com/batch/home?region=ap-southeast-1#jobs)
   and select the "g4dn-xlarge" job queue. You will see "RUNNING" in the Status column. Please note, it takes around 10 - 13
   minutes from submitting the jobs until AWS Batch shows the "RUNNING" state. During this time the Auto Scaling group
   launches EC2 instances and the basecaller container image (several GB in size!) is downloaded from the Elastic Container
   Registry (ECR) and started.


4. **check job log outputs:** Once a job has entered the "RUNNING" state all commandline outputs from the basecallers are
   redirected to CloudWatch Logs. To see the log output, select a running job in the [AWS Batch Jobs console](https://ap-southeast-1.console.aws.amazon.com/batch/home?region=ap-southeast-1#jobs).
   In the "Job information" section select the log stream URL.


You will be redirected to the CloudWatch logs event console where you can inspect the log messages.


5. **Check job has finished:** select a job in the [AWS Batch Jobs console](https://ap-southeast-1.console.aws.amazon.com/batch/home?region=ap-southeast-1#jobs).
   The completion of a job is reported in the "Job information" section. Please note that it takes around 10 - 12 minutes
   for a job to start and another 30 minutes to several hours (depending on instance type) to complete.


## Cleaning up

After concluding the job run, all resources are destroyed by running the following command.

```shell
cdk destroy --all --require-approval never
```

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
