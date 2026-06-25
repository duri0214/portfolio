from django.contrib import admin

from llm_chat.models import ChatLogs, OpenAIRagPdf, RiddleQuestion


admin.site.register(ChatLogs)
admin.site.register(OpenAIRagPdf)
admin.site.register(RiddleQuestion)
