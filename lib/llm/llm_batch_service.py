import json
import os
import secrets

from openai import OpenAI
from openai.types import Batch

from lib.llm.service.completion import LlmService
from lib.llm.valueobject.chat import Message, RoleType
from lib.llm.valueobject.chat_batch import MessageChunk
from lib.llm.valueobject.config import OpenAIGptConfig


# TODO: ファイル名を service/completion_batch.py にリネームする
class OpenAIBatchCompletionService(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    @staticmethod
    def remove_file_if_exists(file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)

    def parse_to_message_chunk(self, messages: list[Message]) -> MessageChunk:
        return MessageChunk(
            messages=messages,
            model=self.config.model,
            max_tokens=self.config.max_tokens,
        )

    @staticmethod
    def export_jsonl_file(chunks: list[MessageChunk]) -> str:
        """
        指定された MessageChunk リストを JSONL 形式に変換して、ローカルファイルとして保存します。

        JSONL 形式の各行には、1つのチャンク（MessageChunk）がシリアライズされた
        JSON エントリが含まれています。

        Args:
            chunks (list[MessageChunk]): JSONL形式に変換する対象のデータチャンクリスト。

        Returns:
            str: 作成された JSONL ファイルの絶対パス。

        Raises:
            RuntimeError: ファイルの作成やデータの書き込み中にエラーが発生した場合。

        Example:
            >>> chunks1 = [
            >>>     MessageChunk(...),
            >>>     MessageChunk(...),
            >>> ]
            >>> file_path1 = OpenAIBatchCompletionService.export_jsonl_file(chunks1)
            >>> print(f"File saved at: {file_path1}")

        Note:
            作成されたファイルは一時的なもので、後続の処理が完了後に削除されることが想定されています。
        """
        file_name = f"export_{secrets.token_hex(5)}.jsonl"
        file_path = os.path.abspath(file_name)
        try:
            with open(file_path, "w", encoding="utf-8") as jsonl_file:
                for chunk in chunks:
                    json_entry = chunk.to_jsonl_entry()
                    jsonl_file.write(json.dumps(json_entry) + "\n")
        except Exception as e:
            raise RuntimeError(f"Failed to export JSONL file: {str(e)}")

        return file_path

    def upload_jsonl_file(self, chunks: list[MessageChunk]) -> str:
        """
        JSONLファイルをOpenAIにアップロードする。

        Args:
            chunks (list[MessageChunk]): アップロードするデータのチャンク。

        Returns:
            str: アップロードされたファイルのID。
        """
        jsonl_file_path = self.export_jsonl_file(chunks)

        try:
            with open(jsonl_file_path, "rb") as jsonl_file:
                uploaded_file = OpenAI(api_key=self.config.api_key).files.create(
                    file=jsonl_file, purpose="batch"
                )
            return uploaded_file.id
        finally:
            self.remove_file_if_exists(jsonl_file_path)

    def create_batch(self, uploaded_file_id: str) -> Batch:
        return OpenAI(api_key=self.config.api_key).batches.create(
            input_file_id=uploaded_file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )

    def retrieve_answer(self, batch_id: str) -> Batch:
        return OpenAI(api_key=self.config.api_key).batches.retrieve(batch_id)

    def retrieve_content(self, file_id: str) -> list[Message]:
        def fetch_file_content(input_file_id: str) -> bytes:
            return (
                OpenAI(api_key=self.config.api_key).files.content(input_file_id).content
            )

        def parse_to_message(json_line: dict) -> Message:
            try:
                choice = json_line["response"]["body"]["choices"][0]
                return Message(
                    role=RoleType(choice["message"]["role"]),
                    content=choice["message"]["content"],
                )
            except (KeyError, ValueError) as e:
                print(f"Error parsing result: {json_line}, error: {e}")

        raw_data = fetch_file_content(file_id)
        file_name = f"retrieve_{secrets.token_hex(5)}.jsonl"
        file_path = os.path.abspath(file_name)
        with open(file_path, "wb") as file:
            file.write(raw_data)

        results: list[Message] = []
        try:
            with open(file_path, "r") as file:
                for line in file:
                    json_object = json.loads(line.strip())
                    results.append(parse_to_message(json_object))
        finally:
            self.remove_file_if_exists(file_path)

        return results


if __name__ == "__main__":
    import time

    # サンプルのMessageChunkデータ
    service = OpenAIBatchCompletionService(
        OpenAIGptConfig(
            api_key="your-api-key",
            model="gpt-4o",
            max_tokens=1000,
            temperature=0.7,
        )
    )
    sample_chunks = [
        service.parse_to_message_chunk(
            [
                Message(role=RoleType.SYSTEM, content="You are a helpful assistant1."),
                Message(role=RoleType.USER, content="What is your name?"),
            ]
        ),
        service.parse_to_message_chunk(
            [
                Message(role=RoleType.SYSTEM, content="You are a helpful assistant2."),
                Message(role=RoleType.USER, content="What is your name?"),
            ]
        ),
    ]

    file_id_test = service.upload_jsonl_file(sample_chunks)
    batch_id_test = service.create_batch(file_id_test).id

    while True:
        result_test = service.retrieve_answer(batch_id_test)
        print(f"Current status: {result_test.status}")
        if result_test.status == "completed":
            print("Batch processing completed!")
            break
        time.sleep(5)

    content_test = service.retrieve_content(result_test.output_file_id)
    print(f"{content_test=}")
