import httpx
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


# 插件配置，根据需要修改
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



# 获取配置实例
config = plugin.get_config(ZaobaoConfig)


class ZaobaoResponse(BaseModel):
    """早报接口响应模型"""
    code: int = Field(..., title="状态码", description="API返回状态码")
    msg: str = Field(..., title="状态说明", description="API返回状态信息")
    data: dict = Field(
        ...,
        title="数据体",
        description="包含date(日期), news(新闻列表), weiyu(励志语句)的字典对象"
    )

@plugin.mount_sandbox_method(
    SandboxMethodType.BEHAVIOR,
    name="获取每日早报",
    description="获取并发送当日早报信息到指定聊天场景"
)
async def send_daily_zuobao(chat_key: str, _ctx: AgentCtx) -> str:
    """获取并发送每日早报内容到指定聊天窗口

    Args:
        chat_key (str): 目标聊天窗口的唯一标识符

    Returns:
        str: 操作结果提示信息

    Raises:
        ValueError: API请求失败或数据解析出错时抛出
        httpx.HTTPError: 网络请求相关异常

    Example:
        send_daily_zuobao("chat_12345")
    """
    try:
        payload = {"token": config.API_TOKEN, "format": "json"}
        headers = {"Content-Type": "application/json"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.API_URL, 
                json=payload, 
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            
        # 解析API响应
        try:
            zaobao_data = ZaobaoResponse.parse_obj(response.json())
        except ValidationError as e:
            logger.error(f"API响应格式验证失败: {str(e)}")
            raise ValueError("早报数据格式异常，请检查API响应")

        # 检查API状态
        if zaobao_data.code != 200:
            logger.error(f"API请求失败[{zaobao_data.code}]: {zaobao_data.msg}")
            raise ValueError(f"API服务返回错误: {zaobao_data.msg}")

        # 数据完整性验证
        required_keys = ("date", "news", "weiyu")
        for key in required_keys:
            if key not in zaobao_data.data:
                logger.error(f"缺失必要字段: {key}")
                raise ValueError(f"早报数据缺失必需字段 {key}")

        # 构建消息内容
        news_list = "\n".join(f"• {item}" for item in zaobao_data.data["news"])
        report_message = (
            f"今天是 {zaobao_data.data['date']}\n"
            f"{news_list}\n"
            f"{zaobao_data.data['weiyu']}"
        )

        # 发送消息到指定聊天
        await message.send_text(chat_key, report_message, ctx=_ctx)
        return "早报已成功发送，愿今日一切顺利！"

    except httpx.RequestError as e:
        logger.error(f"网络请求异常: {str(e)}")
        raise ValueError("无法连接早报服务，请检查网络") from e
    except Exception as e:
        logger.exception("处理早报请求时发生未知错误")
        raise ValueError(f"早报处理异常: {str(e)[:200]}") from e

@plugin.mount_cleanup_method()
async def cleanup_method():
    """清理插件资源"""
    # 这里可以添加资源释放逻辑（如关闭长连接）
    logger.info("早报插件资源已清理")
