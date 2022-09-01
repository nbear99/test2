class ECS:
    def __init__(self, name, boto_session, boto_config):
        self.boto = boto_session.client(
            'ecs',
            config=boto_config
        )
        self.name = name
        self.__cluster_instances()
        self.__cluster_asgs()
   
    def __cluster_instances(self):
        cluster_instances = []
        resp = self.boto.list_container_instances(
            cluster=self.name
        )
        instances = self.boto.describe_container_instances(
            cluster=self.name,
            containerInstances=resp['containerInstanceArns']
        )
        for instance in instances['containerInstances']:
            cluster_instances.append({
                'instance_id': instance['ec2InstanceId'],
                'arn': instance['containerInstanceArn'],
               'running_count': instance['runningTasksCount']
            })
        self.cluster_instances = sorted(cluster_instances, key=lambda k: k['running_count'])
   
    def __cluster_asgs(self):
        self.cluster_asgs = []
        resp = self.boto.describe_clusters(
            clusters=[self.name]
        )
        capacity_providers = self.boto.describe_capacity_providers(
            capacityProviders=resp['clusters'][0]['capacityProviders']
        )
        for provider in capacity_providers['capacityProviders']:
            if provider['status'] == 'ACTIVE':
                asg_name = provider['autoScalingGroupProvider']['autoScalingGroupArn'].split('/')[-1]
                self.cluster_asgs.append(asg_name)
   
    def drain_instance(self, instance):
        self.boto.update_container_instances_state(
            cluster=self.name,
            containerInstances=[instance['arn']],
            status='DRAINING'
        )
   
    def instance_task_count(self, instance):
        resp = self.boto.describe_container_instances(
            cluster=self.name,
            containerInstances=[instance['arn']]
        )
        return resp['containerInstances'][0]['runningTasksCount']
   
    def deregister_instance(self, instance):
        self.boto.deregister_container_instance(
            cluster=self.name,
            containerInstance=instance['arn']
        )

