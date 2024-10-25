import aws_cdk as core
import aws_cdk.assertions as assertions

from basecaller_on_aws.basecaller_on_aws_stack import BasecallerOnAwsStack


# example tests. To run these tests, uncomment this file along with the example
# resource in basecaller_on_aws/basecaller_on_aws_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = BasecallerOnAwsStack(app, "basecaller-on-aws")
    template = assertions.Template.from_stack(stack)


#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
