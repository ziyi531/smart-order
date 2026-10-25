import uuid
from datetime import datetime
from typing import Any, Dict

from app.config import ERP_TARGETS
from app.models import ERPPushResponse, PackagingOrderSchema


class ERPAdapter:
    """Interface for pushing a structured order into an ERP/MES as a manufacturing work order."""

    simulated = False

    def __init__(self, target: Dict[str, Any]):
        self.target = target

    def push(self, order: PackagingOrderSchema, operator: str) -> ERPPushResponse:
        raise NotImplementedError


class MockERPAdapter(ERPAdapter):
    """Stand-in until a real connector exists: generates a bill number locally, nothing is sent."""

    simulated = True

    def push(self, order: PackagingOrderSchema, operator: str) -> ERPPushResponse:
        bill_no = f"{self.target['bill_prefix']}-MO-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        message = (
            f"[模拟] 未连接真实 {self.target['label']}，订单 [{order.header.order_no or '未编号'}] 未被发送；"
            f"仅在本地生成示例单号 {bill_no}（操作人: {operator}）。"
        )
        return ERPPushResponse(
            success=True,
            simulated=True,
            erp_bill_no=bill_no,
            target_erp=self.target["id"],
            message=message,
            pushed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )


def get_erp_adapter(target_id: str) -> ERPAdapter:
    """Resolve a target id from config/erp_targets.json; raises KeyError for unknown targets."""
    for target in ERP_TARGETS:
        if target["id"] == target_id:
            return MockERPAdapter(target)
    raise KeyError(target_id)
