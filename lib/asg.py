class ASG:
    def __init__(self, name, boto_session, boto_config):
        self.boto_asg = boto_session.client(
            'autoscaling',
            config=boto_config
        )
        self.boto_ec2 = boto_session.client(
            'ec2',
            config=boto_config
        )
        self.boto_ssm = boto_session.client(
            'ssm',
            config=boto_config
        )
        self.name = name
        self.__asg_info()
        self.__lt_curr_ami()
        self.__latest_ami()
 
    def __asg_info(self):
        resp = self.boto_asg.describe_auto_scaling_groups(
            AutoScalingGroupNames=[self.name]
        )
        self.instances = [instance['InstanceId'] for instance in resp['AutoScalingGroups'][0]['Instances']]
        if resp['AutoScalingGroups'][0].get('MixedInstancesPolicy') is not None:
            lt = resp['AutoScalingGroups'][0]['MixedInstancesPolicy']['LaunchTemplate']['LaunchTemplateSpecification']
        elif resp['AutoScalingGroups'][0].get('LaunchTemplate') is not None:
            lt = resp['AutoScalingGroups'][0]['LaunchTemplate']
        else:
            return None
        self.lt_name = lt['LaunchTemplateName']
        self.lt_version = lt['Version']
        self.orig_desired = resp['AutoScalingGroups'][0]['DesiredCapacity']
        self.os_name = next(tag['Value'] for tag in resp['AutoScalingGroups'][0]['Tags'] if tag['Key'] == 'OS')
   
    def __lt_curr_ami(self):
        ltv = self.boto_ec2.describe_launch_template_versions(
            LaunchTemplateName=self.lt_name,
            Versions=[str(self.lt_version)]
        )
        self.lt_curr_ami = ltv['LaunchTemplateVersions'][0]['LaunchTemplateData']['ImageId']
        ami = self.boto_ec2.describe_images(
            ImageIds=[self.lt_curr_ami]
        )
        self.platform = ami['Images'][0]['PlatformDetails'].lower()
        self.architecture = ami['Images'][0]['Architecture'].lower()
   
    def __latest_ami(self):
        ami_params = {
            'al2': {
                'arm64': '/aws/service/ecs/optimized-ami/amazon-linux-2/arm64/recommended/image_id',
                'x86_64': '/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id'
            },
            'bottlerocket': {
                'arm64': '/aws/service/bottlerocket/aws-ecs-1/arm64/latest/image_id',
                'x86_64': '/aws/service/bottlerocket/aws-ecs-1/x86_64/latest/image_id'
            },
            'windows': {
                'x86_64': '/aws/service/ami-windows-latest/Windows_Server-2019-English-Full-ECS_Optimized/image_id',
            }
        }
        resp = self.boto_ssm.get_parameter(
            Name=ami_params[self.os_name][self.architecture]
        )
        self.latest_ami = resp['Parameter']['Value']
   
    def instance_ami(self, instance_id):
        instance = self.boto_ec2.describe_instances(
            InstanceIds=[instance_id]
        )
        return instance['Reservations'][0]['Instances'][0]['ImageId']
   
    def curr_capacity(self):
        resp = self.boto_asg.describe_auto_scaling_groups(
            AutoScalingGroupNames=[self.name]
        )
        return resp['AutoScalingGroups'][0]['DesiredCapacity']
   
    def update_launch_template(self):
        resp = self.boto_ec2.create_launch_template_version(
            LaunchTemplateName=self.lt_name,
            SourceVersion=str(self.lt_version),
            VersionDescription='Automated AMI Update',
            LaunchTemplateData={
                'ImageId': self.latest_ami
            }
        )
        self.lt_new_ver = resp['LaunchTemplateVersion']['VersionNumber']
   
    def set_launch_template_version(self):
        self.boto_ec2.modify_launch_template(
            LaunchTemplateName=self.lt_name,
            DefaultVersion=str(self.lt_new_ver)
        )
   
    def detach_instance_from_asg(self, instance_id):
        self.boto_asg.detach_instances(
            InstanceIds=[instance_id],
            AutoScalingGroupName=self.name,
            ShouldDecrementDesiredCapacity=False
        )
   
    def terminate_instance(self, instance_id):
        self.boto_ec2.terminate_instances(
            InstanceIds=[instance_id]
        )
