#==========================================================
#       Manage DNS Records for an Autoscaling Group
#==========================================================
#
# Created by Dave Hawkins, 4 June 2019
#
# Released under the MIT License
#
# This Lambda function receives Lifecycle Transitions
#  from an Autoscale fleet and updates a Route53 Host
#  Record to reflect the current group of available
#  systems.
#
# If function runs without any Autoscale event then
#  it will collect all the Public IPs for instances
#  in the fleet and resets the Route53 Host Record
#  with those IPs.
#
# 
# Note: There are several API calls made to AWS that can
#       cause a delay. I recommend you set the Lambda timeout
#       to 10 seconds or more. In an informal test the 
#       execution time reached 4 seconds.
#
#==========================================================
#        Pre-requisites/Requirements
#==========================================================
#
# Maybe one day I'll build a really fancy CloudFormation
#  template for this function. Until then...
#
#==========================================================
# CLOUD WATCH TRIGGER EVENT
#
# The trigger for this lambda function is CloudWatch with
#  the following event pattern:
#        {
#          "detail-type": [
#            "EC2 Instance-launch Lifecycle Action"
#          ],
#          "source": [
#            "aws.autoscaling"
#          ]
#        }
#
#==========================================================
# IAM ROLE PERMISSIONS
#
# I highly recommend tailoring the generic AWS policies
#  to scope to the specific read/write requirements for
#  your resources. At a fundamental level the lambda
#  role requires:
#
#  - Write permissions to Route53 Zone
#  - Read permissions to EC2
#  - Write permissions to AutoScaling
#
#==========================================================
# ENVIRONMENT VARIABLES
#
# The Lambda function must be configured with the
#  following environment variables:
#
# ZONE_ID = <YOUR ZONE ID>
# HOSTRECORD = <hostname.domain.tld.> (including the trailing '.')
# AUTOSCALING_GROUP_NAME = <string>
#

import json
import boto3
import os


# Get the public IP address of the instance
def getIPofInstance(instanceId):
    ec2 = boto3.resource('ec2')
    instance = ec2.Instance(instanceId)
    instance.load()
    return instance.public_ip_address

    
#  Tell the autoscaling api to continue the transition event for the instance
def resumeAutoscaleTransition(autoscaleGroupName, autoscaleLifecycleHookName, instanceId):
    client = boto3.client('autoscaling')
    response = client.complete_lifecycle_action(
        LifecycleHookName=autoscaleLifecycleHookName,
        AutoScalingGroupName=autoscaleGroupName,
        LifecycleActionResult='CONTINUE',
        InstanceId=instanceId
    )
    return True


# Return the Route53 RecordSet for the IP Addresses currently registered.
def getIpAddressesFromRoute53Entry(route53ZoneId, hostRecordToMaintain):
    client = boto3.client('route53')
    currentRecordSets = client.list_resource_record_sets(HostedZoneId=route53ZoneId)
    
    resourceRecordSet = {}
    for recordSet in currentRecordSets["ResourceRecordSets"]:
        if ((recordSet["Name"] == hostRecordToMaintain) and (recordSet["Type"] == "A")):
            currentResourceRecordSet = recordSet
    
    ipAddresses = []
    for resourceRecord in resourceRecordSet:
        ipAddresses.append(resourceRecord["Value"])
    
    return ipAddresses

    
# Set the Route53 RecordSet to the IP Addresses provided.
def setDNSRecord(route53ZoneId, hostRecordToMaintain, ipAddresses = []):
    client = boto3.client('route53')
    
    resourceRecords = []
    for ipAddress in ipAddresses:
        resourceRecords.append({"Value": ipAddress})
    
    resourceRecordSet={
          "Name": hostRecordToMaintain,
          "Type": "A",
          "TTL": 300,
          "ResourceRecords": resourceRecords
        }
    
    response = client.change_resource_record_sets(
        HostedZoneId=route53ZoneId,
        ChangeBatch={
            'Comment': 'Adding new host to group',
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': resourceRecordSet
                }
            ]
        }
    )


# Assume the DNS record is compromised. Rebuild it based on the current autoscaling group running
def baselineIpAddressesInDNS(route53ZoneId, hostRecordToMaintain, autoscaleGroupName):
    # To be implemented:
    # - Query the autoscalingGroup for all instances,
    # - Collect all the public IP addresses for instances,
    # - Reset the hostRecord of the route53Zone with the current instance public IPs.
    client = boto3.client('autoscaling')
    response = client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[autoscaleGroupName]
    )
    
    ipAddresses = []
    
    for instance in response["AutoScalingGroups"][0]["Instances"]:
        ipAddresses.append(getIPofInstance(instance["InstanceId"]))
    
    setDNSRecord(route53ZoneId, hostRecordToMaintain, ipAddresses)
        
    return ""


#==========================================================
#       Load environment variables
#==========================================================
route53ZoneId = os.environ.get('ZONE_ID')
hostRecordToMaintain = os.environ.get('HOSTRECORD')
autoscaleGroupName = os.environ.get('AUTOSCALING_GROUP_NAME')


#==========================================================
#       Main routine
#==========================================================
def lambda_handler(event, context):
    
    try:
        if (("source" in event)
            and (event["source"] == "aws.autoscaling")
            and (event["detail-type"] == "EC2 Instance-launch Lifecycle Action")
            and ("EC2InstanceId" in event["detail"])):
            
            instanceId = event["detail"]["EC2InstanceId"]
            lifecycleTransition = event["detail"]["LifecycleTransition"]
            autoscaleLifecycleHookName = event["detail"]["LifecycleHookName"]
            
            newInstancePublicIP = getIPofInstance(instanceId)
                
            if (lifecycleTransition == "autoscaling:EC2_INSTANCE_LAUNCHING"):
                ipAddresses = getIpAddressesFromRoute53Entry(route53ZoneId, hostRecordToMaintain)
                ipAddresses.append(newInstancePublicIP)
                setDNSRecord(route53ZoneId, hostRecordToMaintain, ipAddresses)
                print("Success: Host record updated to include the new instance public IP address.")
                
            elif (lifecycleTransition == "autoscaling:EC2_INSTANCE_TERMINATING"):
                ipAddresses = getIpAddressesFromRoute53Entry(route53ZoneId, hostRecordToMaintain)
                ipAddresses.remove(newInstancePublicIP)
                setDNSRecord(route53ZoneId, hostRecordToMaintain, ipAddresses)
                print("Success: Host record updated to remove the retiring instance public IP address.")
                
            else:
                print("Error: No valid lifecycle transition identified.")
                    
            resumeAutoscaleTransition(autoscaleGroupName, autoscaleLifecycleHookName, instanceId)
            
        else:
            baselineIpAddressesInDNS(route53ZoneId, hostRecordToMaintain, autoscaleGroupName)
            print("Success: Host record reset with current instance public IP addresses for autoscale group.")
        
    except Exception as e:
        print("Error: An exception occured: " + str(e))
        
    finally:
        return ""
