"""
ユースケースタイプの値オブジェクト

アプリケーション層で使用されるユースケースタイプを定義します。
これらは実際のLLMモデル名（ModelName）とは異なり、
アプリケーション上のユースケースを表します。
"""


class UseCaseType:
    """ユースケースタイプの定数クラス"""

    OPENAI_GPT = "OpenAIGpt"
    OPENAI_GPT_STREAMING = "OpenAIGptStreaming"
    GEMINI = "Gemini"
    OPENAI_IMAGE = "OpenAIImage"
    OPENAI_TEXT_TO_SPEECH = "OpenAITextToSpeech"
    OPENAI_SPEECH_TO_TEXT = "OpenAISpeechToText"
    OPENAI_RAG = "OpenAIRag"
    RIDDLE = "Riddle"
