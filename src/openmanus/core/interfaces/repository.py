"""
@PURPOSE: 定义泛型存储库接口协议
@OUTLINE:
    - protocol IRepository[T, ID]: 基础 CRUD 接口
    - protocol IQueryableRepository: 可查询存储库接口
    - protocol ITaskRepository: Task 专用存储库接口
@DEPENDENCIES:
    - 外部: typing (Protocol, Generic, TypeVar)
"""

from typing import Generic, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
ID = TypeVar("ID", bound=str)


@runtime_checkable
class IRepository(Protocol, Generic[T, ID]):
    """
    泛型存储库接口

    提供 CRUD 操作的统一抽象。

    Example:
        >>> class TaskRepository(IRepository[Task, str]):
        ...     async def get(self, id: str) -> Task | None:
        ...         ...
    """

    async def get(self, id: ID) -> T | None:
        """
        根据 ID 获取实体

        Args:
            id: 实体 ID

        Returns:
            实体，不存在返回 None
        """
        ...

    async def get_many(self, ids: list[ID]) -> list[T]:
        """
        批量获取实体

        Args:
            ids: ID 列表

        Returns:
            实体列表 (可能少于请求数量)
        """
        ...

    async def save(self, entity: T) -> T:
        """
        保存实体 (创建或更新)

        Args:
            entity: 实体

        Returns:
            保存后的实体
        """
        ...

    async def save_many(self, entities: list[T]) -> list[T]:
        """
        批量保存实体

        Args:
            entities: 实体列表

        Returns:
            保存后的实体列表
        """
        ...

    async def delete(self, id: ID) -> bool:
        """
        删除实体

        Args:
            id: 实体 ID

        Returns:
            是否成功删除
        """
        ...

    async def exists(self, id: ID) -> bool:
        """
        检查实体是否存在

        Args:
            id: 实体 ID

        Returns:
            是否存在
        """
        ...


@runtime_checkable
class IQueryableRepository(IRepository[T, ID], Protocol):
    """
    可查询存储库接口

    在基础 CRUD 上增加查询能力。
    """

    async def find_by(self, **criteria: object) -> list[T]:
        """
        根据条件查询

        Args:
            **criteria: 查询条件 (字段=值)

        Returns:
            匹配的实体列表
        """
        ...

    async def find_one_by(self, **criteria: object) -> T | None:
        """
        根据条件查询单个

        Args:
            **criteria: 查询条件

        Returns:
            匹配的实体，无则返回 None
        """
        ...

    async def count(self, **criteria: object) -> int:
        """
        根据条件计数

        Args:
            **criteria: 查询条件

        Returns:
            匹配数量
        """
        ...

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """
        分页列出所有

        Args:
            limit: 每页数量
            offset: 偏移量

        Returns:
            实体列表
        """
        ...


@runtime_checkable
class ITaskRepository(Protocol):
    """
    Task 存储库接口

    Task 特定的存储操作。
    """

    async def get(self, task_id: str) -> "Task | None":  # noqa: F821
        """获取任务"""
        ...

    async def save(self, task: "Task") -> "Task":  # noqa: F821
        """保存任务"""
        ...

    async def update_status(self, task_id: str, status: str) -> None:
        """更新状态"""
        ...

    async def find_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list["Task"]:  # noqa: F821
        """根据租户查询"""
        ...

    async def find_running(self) -> list["Task"]:  # noqa: F821
        """查询所有运行中的任务"""
        ...
