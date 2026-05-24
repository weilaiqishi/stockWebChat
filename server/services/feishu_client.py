# -*- coding: utf-8 -*-
"""Feishu (Lark) bitable client — simplified for stockWebChat.

Only handles 3 tables:
  - agent_conversations: session_id, title, messages_json, created_at
  - stock_chat_strategies: strategy_id, name, category, instructions, is_active, created_at
  - stock_analysis_reports: report_id, stock_code, stock_name, report_content, conversation_id, strategy_id, created_at
"""
from typing import Any


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, bitable_id: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self.bitable_id = bitable_id
        self._client = None
        self._table_ids: dict[str, str] = {}

    @property
    def client(self):
        if self._client is None:
            import lark_oapi as lark
            self._client = (
                lark.Client.builder()
                .app_id(self.app_id)
                .app_secret(self.app_secret)
                .log_level(lark.LogLevel.WARNING)
                .build()
            )
        return self._client

    async def validate_and_init(self) -> dict:
        """Validate credentials and create/verify bitable + tables.

        Returns: {bitable_id: str} or {error: str}
        """
        try:
            if not self.bitable_id:
                self.bitable_id = await self._create_bitable()

            # Verify access
            await self._get_table_map()

            # Create missing tables
            await self._ensure_tables()

            return {"bitable_id": self.bitable_id}
        except Exception as e:
            return {"error": f"飞书连接失败: {e}"}

    async def _create_bitable(self) -> str:
        from lark_oapi.api.bitable.v1 import CreateAppRequest, ReqApp
        req = CreateAppRequest.builder().request_body(
            ReqApp.builder().name("策略问股").build()
        ).build()
        resp = self.client.bitable.v1.app.create(req)
        if resp.code != 0:
            raise Exception(f"创建多维表格失败: {resp.msg}")
        return resp.data.app.app_token

    async def _get_table_map(self) -> dict[str, str]:
        from lark_oapi.api.bitable.v1 import ListAppTableRequest
        req = ListAppTableRequest.builder().app_token(self.bitable_id).build()
        resp = await self.client.bitable.v1.app_table.alist(req)
        if resp.code != 0:
            raise Exception(f"获取表格列表失败: {resp.msg}")
        items = getattr(resp.data, "items", []) or []
        table_ids = {}
        for item in items:
            table_ids[item.name] = item.table_id
        self._table_ids = table_ids
        return table_ids

    async def _ensure_tables(self) -> None:
        schemas = {
            "agent_conversations": [
                ("session_id", "text"), ("title", "text"),
                ("messages_json", "text"), ("created_at", "text"),
            ],
            "stock_chat_strategies": [
                ("strategy_id", "text"), ("name", "text"),
                ("category", "text"), ("instructions", "text"),
                ("is_active", "number"), ("created_at", "text"),
            ],
            "stock_analysis_reports": [
                ("report_id", "text"), ("stock_code", "text"),
                ("stock_name", "text"), ("report_content", "text"),
                ("conversation_id", "text"), ("strategy_id", "text"),
                ("created_at", "text"),
            ],
        }

        for table_name, fields in schemas.items():
            if table_name in self._table_ids:
                continue
            # Create table
            from lark_oapi.api.bitable.v1 import (
                CreateAppTableRequest, ReqTable, AppTableField,
            )
            _FIELD_TYPE_MAP = {"text": 1, "number": 2}
            field_list = []
            for fname, ftype in fields:
                field_list.append(
                    AppTableField.builder()
                    .field_name(fname).type(_FIELD_TYPE_MAP.get(ftype, 1)).build()
                )
            req = CreateAppTableRequest.builder().app_token(self.bitable_id).request_body(
                ReqTable.builder()
                .name(table_name)
                .fields(field_list)
                .build()
            ).build()
            resp = self.client.bitable.v1.app_table.create(req)
            if resp.code != 0:
                print(f"[feishu] Failed to create table {table_name}: {resp.msg}")
            else:
                self._table_ids[table_name] = resp.data.table_id
