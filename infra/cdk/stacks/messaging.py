from aws_cdk import Duration, Stack
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class MessagingStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.dlq = sqs.Queue(
            self,
            f'Dlq{env_name}',
            queue_name=f'finsight-{env_name}-dlq',
        )
        self.ingestion = sqs.Queue(
            self,
            f'IngestionQueue{env_name}',
            queue_name=f'finsight-{env_name}-ingestion',
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=self.dlq),
            visibility_timeout=Duration.minutes(15),
        )
        self.reprocessing = sqs.Queue(
            self,
            f'ReprocessingQueue{env_name}',
            queue_name=f'finsight-{env_name}-reprocessing',
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=self.dlq),
            visibility_timeout=Duration.minutes(15),
        )
        self.reports = sqs.Queue(
            self,
            f'ReportsQueue{env_name}',
            queue_name=f'finsight-{env_name}-reports',
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=self.dlq),
            visibility_timeout=Duration.minutes(30),
        )
