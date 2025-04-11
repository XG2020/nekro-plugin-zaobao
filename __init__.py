import httpx
from typing import List
from pydantic import BaseModel, ValidationError, Field

from nekro_agent.services.plugin.base import (
    NekroPlugin,
    ConfigBase,
    SandboxMethodType,
)
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.core import logger


plugin = NekroPlugin(
    name="今日早报",
    module_name="zaobao",
    description="获取每日新闻头条和励志微语的早报服务",
    version="1.0.0",  
    author="XGGM",
    url="https://github.com/XG2020/nekro-plugin-zaobao",
)


@plugin.mount_config()
class ZaobaoConfig(ConfigBase):
    """早报插件配置"""
    API_TOKEN: str = Field(
        default="你的API令牌",
        title="API接口令牌",
        description="访问Alapi.cn接口所需的认证令牌",
    )
    API_URL: str = Field(
        default="https://v3.alapi.cn/api/zaobao",
        title="API接口地址",
        description="早报数据服务API的请求地址",
    )
    TIMEOUT: int = Field(
        default=15,
        title="请求超时时间",
        description="API请求的超时时间(秒)",
    )


# 获取配置实例
config = plugin.get_config(ZaobaoConfig)


class ZaobaoData(BaseModel):
    """早报数据模型"""
    date: str = Field(..., title="日期", description="早报日期，格式为YYYY-MM-DD")
    news: List[str] = Field(..., title="新闻列表", description="当日新闻条目列表")
    weiyu: str = Field(..., title="励志语句", description="每日励志短语")


class ZaobaoResponse(BaseModel):
    """早报接口响应模型"""
    code: int = Field(..., title="状态码", description="API返回状态码")
    msg: str = Field(..., title="状态说明", description="API返回状态信息")
    data: ZaobaoData = Field(..., title="数据体", description="包含日期、新闻和励志语句的完整数据")


@plugin.mount_sandbox_method(
    SandboxMethodType.BEHAVIOR,
    name="获取每日早报",
    description="获取并发送当日早报信息到指定聊天场景"
)
async def send_daily_zuobao(chat_key: str, _ctx: AgentCtx) -> str:
    """获取并发送每日早报内容到指定聊天窗口

    Args:
        chat_key: 目标聊天窗口的唯一标识符

    Returns:
        str: 操作结果提示信息，成功返回"早报发送成功"，失败返回错误原因

    Raises:
        ValueError: 当参数不合法或数据验证失败时抛出
        httpx.HTTPError: 当网络请求失败时抛出

    Example:
        send_daily_zuobao("chat_12345")
    """
    try:
        # 验证输入参数
        if not chat_key or not isinstance(chat_key, str):
            raise ValueError("聊天窗口标识符不能为空且必须是字符串")

        payload = {"token": config.API_TOKEN, "format": "json"}
        headers = {"Content-Type": "application/json"}
        
        # 发起API请求
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.API_URL,
                json=payload,
                headers=headers,
                timeout=config.TIMEOUT
            )
            response.raise_for_status()
            
            # 尝试解析并验证响应数据
            try:
                zaobao_data = ZaobaoResponse.parse_obj(response.json())
            except ValidationError as e:
                logger.error(f"API响应格式验证失败: {str(e)}")
                logger.debug(f"原始API响应: {response.text[:500]}")
                raise ValueError("早报数据格式异常，接口返回数据不符合预期格式")

            # 检查API状态码
            if zaobao_data.code != 200:
                logger.error(f"API请求失败[{zaobao_data.code}]: {zaobao_data.msg}")
                raise ValueError(f"早报服务返回错误: {zaobao_data.msg}")

            # 检查新闻列表是否为空
            if not zaobao_data.data.news:
                logger.warning("早报新闻列表为空")
                zaobao_data.data.news = ["今日暂无重要新闻"]

            # 构建消息内容
            news_list = "\n".join(f"• {item}" for item in zaobao_data.data.news)
            report_message = (
                f"今天是 {zaobao_data.data.date}\n"
                f"{news_list}\n"
                f"{zaobao_data.data.weiyu}"
            )

            # 发送消息到指定聊天
            await _ctx.message.send_text(chat_key, report_message)
            return "早报发送成功"

    except httpx.RequestError as e:
        error_msg = f"网络请求异常: {str(e)}"
        logger.error(error_msg)
        raise ValueError("无法连接到早报服务，请检查网络连接") from e
    except ValueError as e:
        raise  # 直接抛出已经处理过的ValueError
    except Exception as e:
        error_msg = f"处理早报请求时发生未知错误: {str(e)}"
        logger.exception(error_msg)
        raise ValueError("处理早报时发生意外错误") from e


@plugin.mount_cleanup_method()
async def cleanup_method():
    """清理插件资源"""
    logger.info("早报插件资源已清理")
