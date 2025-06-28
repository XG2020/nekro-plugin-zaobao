"""每日早报插件

提供每日早报信息，包括新闻头条、微语和可能的音频链接。
使用 alapi.cn 的 API 获取早报数据。
"""

from typing import Dict, List, Optional, Union
import httpx
from pydantic import BaseModel, Field, ValidationError

from nekro_agent.services.plugin.base import NekroPlugin, ConfigBase, SandboxMethodType
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.core import logger

# 插件实例
plugin = NekroPlugin(
    name="每日早报插件",
    module_name="nekro-plugin-zaobao",
    description="提供每日早报信息，包括新闻头条和微语",
    version="1.0.1", 
    author="XGGM",
    url="https://github.com/XG2020/nekro-plugin-zaobao",
)

@plugin.mount_config()
class ZaobaoConfig(ConfigBase):
    """早报插件配置"""
    API_TOKEN: str = Field(
        default="None",
        title="API令牌",
        description="<a href='https://www.alapi.cn/api/67/api_document' target='_blank'>点击获取API令牌</a> alapi.cn的访问令牌",
    )
    API_URL: str = Field(
        default="https://v3.alapi.cn/api/zaobao",
        title="API地址",
        description="早报API的基础URL",
    )
    TIMEOUT: int = Field(
        default=10,
        title="请求超时时间",
        description="API请求的超时时间(秒)",
    )

class ZaobaoResponse(BaseModel):
    """早报接口响应模型"""
    code: int = Field(..., description="API 返回的状态码")
    msg: str = Field(default="", description="API 返回的消息")
    data: Dict[str, Optional[Union[str, List[str], None]]] = Field(
        default_factory=dict,
        description="早报数据，包含日期、新闻、微语等字段"
    )

@plugin.mount_sandbox_method(
    SandboxMethodType.BEHAVIOR,
    name="获取每日早报",
    description="获取最新的每日早报信息，包括新闻头条和微语",
)
async def get_daily_zaobao(_ctx: AgentCtx) -> str:
    """获取最新的每日早报信息
    
    Returns:
        str: 早报信息字符串，包含日期、新闻头条和微语
        如果获取失败，返回错误信息字符串
        
    Raises:
        ValueError: 如果 API 返回关键数据缺失
        
    Example:
        get_daily_zaobao()
    """
    # 获取配置
    config = plugin.get_config(ZaobaoConfig)
    
    # 准备请求参数
    payload = {"token": config.API_TOKEN, "format": "json"}
    headers = {"Content-Type": "application/json"}
    
    try:
        async with httpx.AsyncClient(timeout=config.TIMEOUT) as client:
            # 发送API请求
            response = await client.post(config.API_URL, json=payload, headers=headers)
            response.raise_for_status()
            
            try:
                # 验证响应数据（使用更宽松的模型定义）
                zaobao_data = ZaobaoResponse(**response.json())
            except ValidationError as e:
                logger.error(f"API 响应数据格式错误: {str(e)}")
                return "早报数据格式不正确，请稍后重试。"
            
            if zaobao_data.code != 200:
                logger.error(f"API 返回错误: {zaobao_data.msg}")
                return f"获取早报失败: {zaobao_data.msg}"
            
            # 检查必须字段
            required_fields = ['date', 'news', 'weiyu']
            for field in required_fields:
                if field not in zaobao_data.data or not zaobao_data.data[field]:
                    logger.error(f"早报数据缺失关键字段: {field}")
                    return f"早报数据不完整，缺少 {field} 信息，请稍后重试。"
            
            try:
                # 处理新闻列表数据
                news_data = zaobao_data.data['news']
                if isinstance(news_data, list):
                    news = "\n".join(news_data)
                elif isinstance(news_data, str):
                    news = news_data
                else:
                    news = "【暂无详细新闻】"
                
                # 构建早报信息
                result = [
                    f"【每日早报】",
                    f"今天是 {zaobao_data.data['date']}",
                    news,
                    zaobao_data.data['weiyu']
                ]
                
                # 可选：添加音频链接（如果有）
                if zaobao_data.data.get('audio') and zaobao_data.data['audio'] is not None:
                    result.append(f"\n音频链接: {zaobao_data.data['audio']}")
                
                return "\n".join(result)
            except Exception as e:
                logger.error(f"早报信息拼接失败: {str(e)}")
                return "早报信息处理失败，请稍后重试。"
    except httpx.RequestError as e:
        logger.error(f"HTTP 请求失败: {str(e)}")
        return "无法连接到早报服务，请稍后重试。"
    except Exception as e:
        logger.error(f"处理早报信息时出错: {str(e)}")
        return "处理早报信息时出错，请稍后重试。"

@plugin.mount_cleanup_method()
async def clean_up():
    """清理插件资源"""
    logger.info("早报插件资源已清理")
