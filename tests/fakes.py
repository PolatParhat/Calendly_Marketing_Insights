"""Small in-memory stand-ins for the AWS clients the Lambdas use (no AWS account needed)."""

from botocore.exceptions import ClientError


class FakeS3:
    def __init__(self, fail_puts: bool = False):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.fail_puts = fail_puts

    def put_object(self, Bucket, Key, Body, ContentType=None):
        if self.fail_puts:
            raise ClientError({"Error": {"Code": "InternalError"}}, "PutObject")
        self.objects[(Bucket, Key)] = Body

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}


class FakeSQS:
    def __init__(self, fail: bool = False):
        self.messages: list[dict] = []
        self.fail = fail
        self._next = 0

    def send_message(self, QueueUrl, MessageBody):
        if self.fail:
            raise ClientError({"Error": {"Code": "InternalError"}}, "SendMessage")
        self._next += 1
        self.messages.append({"Body": MessageBody, "ReceiptHandle": str(self._next)})

    def receive_message(self, QueueUrl, MaxNumberOfMessages, WaitTimeSeconds):
        return {"Messages": list(self.messages[:MaxNumberOfMessages])}

    def delete_message(self, QueueUrl, ReceiptHandle):
        self.messages = [m for m in self.messages if m["ReceiptHandle"] != ReceiptHandle]


class FakeSecrets:
    def __init__(self, value: str):
        self.value = value

    def get_secret_value(self, SecretId):
        return {"SecretString": self.value}
