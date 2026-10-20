from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.chat_models.tongyi import BaseChatModel
from utils.config_handler import rag_conf
class BaseModelFactory(ABC):
    @abstractmethod
    def get_model(self)->Optional[Embeddings | BaseChatModel ]:
        pass

class ChatModelFactory(BaseModelFactory):
    def get_model(self)->Optional[Embeddings | BaseChatModel ]:
        return ChatTongyi(model=rag_conf["chat_model_name"])

class EmbeddingsFactory(BaseModelFactory):
    def get_model(self)->Optional[Embeddings | BaseChatModel ]:
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])

chat_model = ChatModelFactory().get_model()
embed_model = EmbeddingsFactory().get_model()