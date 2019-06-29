# Utility methods to make using Boto3 a little more consistent
#
# All AWS Resources have an ARN. This ARN is used to uniquely
# identify the resource (like a serial number or national id)
#
# Unfortunately, most Boto3 functions cannot receive the ARN
#
# This utility helps convert ARNs into Boto3-useful data
#
# Why do I care? Because I would like to be able to identify
#  all required resource dependencies purely by ARN!
#
# WARNING: This 'release' contains _ZERO_ VALIDATION
#  All ARNs are assumed to be valid for the resource type!

def breakDownARN(arn):
    retVal = {
        "ARN": arn,
        "Partition": None,
        "Service": None,
        "Region": None,
        "AccountId": None,
        "ResourceType": None,
        "Resource": None,
        "Qualifier": None
    }
    
    arn = arn.replace("/", ":")
    arnParts = arn.split(":")
    
    # Reading past the array length will cause an Exception
    # But that's perfectly fine. We've already saftied the return value...
    
    
    try:
        retVal["Partition"] = arnParts[1]
        retVal["Service"] = arnParts[2]
        retVal["Region"] = arnParts[3]
        retVal["AccountId"] = arnParts[4]
        
        # There is one strange exception per https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
        # If there are only 6 elements to the array, the 6th element should be the Resource (not the ResourceType)
        if len(arnParts) == 6:
            # This is an older style ARN, Resource is the 6th element:
            retVal["Resource"] = arnParts[5]
        else:
            # This is a newer style ARN, ResourceType is the 6th element:
            retVal["ResourceType"] = arnParts[5]
            retVal["Resource"] = arnParts[6]
        
        retVal["Qualifier"] = arnParts[7]
    except:
        pass
        
    # Exceptions to the rule get handled here...
    
    # It turns out that AutoScaling groups have an extra part.
    # And... Boto3 needs that last part. We'll make it the "qualifier"
    if retVal["Service"] == "autoscaling" and retVal["ResourceType"] == "autoScalingGroup":
        retVal["Qualifier"] = arnParts[-1]
    
    return retVal

    
def getResourceFromARN(arn):
    return breakDownARN(arn)["Resource"]

def getQualifierFromARN(arn):
    return breakDownARN(arn)["Qualifier"]

def getDynamoTableName(arn):
    return getResourceFromARN(arn)
    
def getLambdaFunctionName(arn):
    return getResourceFromARN(arn)
    
def getS3Bucket(arn):
    return getResourceFromARN(arn)
    
def getAutoscaleGroupName(arn):
    return getQualifierFromARN(arn)

def getSqsQueueUrl(arn):
    # Break down the parts of the ARN to generate the SQS Queue URL
    
    parts = breakDownARN(arn)
    url = ("https://" +
            parts["Service"] + "." +
            parts["Region"] + ".amazonaws.com/" +
            parts["AccountId"] + "/" +
            parts["Resource"]
    )
    return url

def getSqsQueueName(arn):
    return getResourceFromARN(arn)
