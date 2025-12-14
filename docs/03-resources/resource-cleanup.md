# 资源清理

## 概述

资源清理器负责在资源释放时执行类型特定的清理策略，确保资源可以安全复用。

## 资源生命周期状态机

```
INITIALIZING → IDLE ⇄ LEASED
                ↓       ↓
            RELEASING ← ┘
                ↓
           TERMINATED

Any State → UNHEALTHY → RELEASING → TERMINATED
```

### 状态定义

```python
class ResourceState(Enum):
    INITIALIZING = 'initializing'  # 初始化中
    IDLE = 'idle'                  # 空闲可用
    LEASED = 'leased'              # 已被租用
    RELEASING = 'releasing'        # 释放中
    UNHEALTHY = 'unhealthy'        # 不健康
    TERMINATED = 'terminated'      # 已终止
```

### 状态转换

```python
class ResourceLifecycle:
    """资源生命周期状态机"""

    TRANSITIONS = {
        ResourceState.INITIALIZING: [ResourceState.IDLE, ResourceState.UNHEALTHY],
        ResourceState.IDLE: [ResourceState.LEASED, ResourceState.RELEASING, ResourceState.UNHEALTHY],
        ResourceState.LEASED: [ResourceState.IDLE, ResourceState.RELEASING, ResourceState.UNHEALTHY],
        ResourceState.RELEASING: [ResourceState.TERMINATED, ResourceState.UNHEALTHY],
        ResourceState.UNHEALTHY: [ResourceState.RELEASING],
        ResourceState.TERMINATED: [],
    }

    async def transition(self, resource: Resource, to_state: ResourceState) -> bool:
        if to_state not in self.TRANSITIONS[resource.state]:
            raise InvalidTransitionError(
                f"Cannot transition from {resource.state} to {to_state}"
            )

        old_state = resource.state
        resource.state = to_state
        resource.state_changed_at = datetime.utcnow()

        await self._on_state_change(resource, old_state, to_state)
        return True

    async def _on_state_change(self, resource: Resource, old: ResourceState, new: ResourceState):
        if new == ResourceState.RELEASING:
            asyncio.create_task(self._cleanup_resource(resource))
        elif new == ResourceState.UNHEALTHY:
            asyncio.create_task(self._handle_unhealthy(resource))

        await self.event_bus.emit(ResourceStateChangedEvent(resource, old, new))
```

## 资源清理器

```python
class ResourceCleaner:
    """资源清理器 - 不同类型资源的清理策略"""

    def __init__(self):
        self.cleaners = {
            ResourceType.BROWSER: BrowserCleaner(),
            ResourceType.MOBILE: MobileCleaner(),
            ResourceType.CONTAINER: ContainerCleaner(),
            ResourceType.VM: VMCleaner(),
        }

    async def cleanup(self, resource: Resource) -> CleanupResult:
        cleaner = self.cleaners.get(resource.type)
        if not cleaner:
            raise ValueError(f"No cleaner for resource type: {resource.type}")
        return await cleaner.cleanup(resource)
```

## 浏览器清理

```python
class BrowserCleaner:
    """浏览器资源清理"""

    async def cleanup(self, resource: BrowserResource) -> CleanupResult:
        result = CleanupResult(resource_id=resource.id)

        try:
            driver = await self._get_driver(resource)

            # 1. 关闭所有标签页（保留主标签）
            windows = await driver.get_window_handles()
            for window in windows[1:]:
                await driver.switch_to.window(window)
                await driver.close()

            # 2. 清除浏览器状态
            await driver.delete_all_cookies()
            await driver.execute_script("window.localStorage.clear();")
            await driver.execute_script("window.sessionStorage.clear();")

            # 3. 清除缓存（CDP）
            if hasattr(driver, 'execute_cdp_cmd'):
                await driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                await driver.execute_cdp_cmd('Network.clearBrowserCookies', {})

            # 4. 导航到空白页
            await driver.get('about:blank')

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)
            await self.resource_lifecycle.transition(resource, ResourceState.UNHEALTHY)

        return result
```

### 浏览器清理检查项

| 项目 | 清理方式 | 说明 |
|-----|---------|-----|
| 标签页 | 关闭非主标签 | 保留一个空白标签 |
| Cookies | `delete_all_cookies()` | 清除所有域的 cookies |
| LocalStorage | `localStorage.clear()` | 清除本地存储 |
| SessionStorage | `sessionStorage.clear()` | 清除会话存储 |
| 缓存 | CDP `clearBrowserCache` | 清除浏览器缓存 |
| 页面 | 导航到 `about:blank` | 重置到空白页 |

## 容器清理

```python
class ContainerCleaner:
    """容器资源清理"""

    async def cleanup(self, resource: ContainerResource) -> CleanupResult:
        result = CleanupResult(resource_id=resource.id)

        try:
            k8s = self.k8s_client

            # 1. 停止运行中的进程
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['pkill', '-9', '-f', '.'])

            # 2. 清理临时文件
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['rm', '-rf', '/tmp/*', '/var/tmp/*'])

            # 3. 清理工作目录
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['rm', '-rf', f'{resource.work_dir}/*'])

            # 4. 重置网络连接
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['ss', '-K'])

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)
            # 清理失败则重建容器
            await self._recreate_container(resource)

        return result
```

### 容器清理检查项

| 项目 | 清理方式 | 说明 |
|-----|---------|-----|
| 进程 | `pkill -9` | 终止所有用户进程 |
| 临时文件 | `rm -rf /tmp/*` | 清理临时目录 |
| 工作目录 | `rm -rf work_dir/*` | 清理任务产物 |
| 网络连接 | `ss -K` | 断开所有连接 |
| 失败处理 | 重建 Pod | 清理失败则删除重建 |

## 手机清理

```python
class MobileCleaner:
    """手机资源清理"""

    async def cleanup(self, resource: MobileResource) -> CleanupResult:
        result = CleanupResult(resource_id=resource.id)

        try:
            appium = self.appium_client

            # 1. 关闭测试应用
            await appium.terminate_app(resource.test_app_package)

            # 2. 清除应用数据
            if resource.kind == 'sim':
                await appium.reset_app(resource.test_app_package)

            # 3. 返回主屏
            await appium.press_keycode('HOME')

            # 4. 清理通知
            await appium.open_notifications()
            await appium.clear_all_notifications()

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result
```

## VM 清理

```python
class VMCleaner:
    """虚拟机资源清理"""

    async def cleanup(self, resource: VMResource) -> CleanupResult:
        result = CleanupResult(resource_id=resource.id)

        try:
            ssh = await self._get_ssh_client(resource)

            # 1. 终止用户进程
            await ssh.run('pkill -u task_user')

            # 2. 清理工作目录
            await ssh.run(f'rm -rf {resource.work_dir}/*')

            # 3. 清理临时文件
            await ssh.run('rm -rf /tmp/task_*')

            # 4. 重置网络规则
            await ssh.run('iptables -F OUTPUT')

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)
            # 考虑快照恢复
            await self._restore_snapshot(resource)

        return result
```

## 清理结果

```python
@dataclass
class CleanupResult:
    resource_id: str
    success: bool = False
    error: Optional[str] = None
    cleaned_items: List[str] = field(default_factory=list)
    duration_ms: int = 0
```

## 清理策略配置

```yaml
cleanup:
  browser:
    clear_cookies: true
    clear_storage: true
    clear_cache: true
    navigate_blank: true
    timeout_ms: 10000

  container:
    kill_processes: true
    clean_temp: true
    clean_work_dir: true
    reset_network: true
    timeout_ms: 30000
    recreate_on_failure: true

  mobile:
    terminate_app: true
    clear_app_data: false    # 真机不清理数据
    clear_app_data_sim: true # 模拟器清理数据
    return_home: true
    timeout_ms: 15000

  vm:
    kill_user_processes: true
    clean_work_dir: true
    clean_temp: true
    reset_network_rules: true
    snapshot_restore_on_failure: true
    timeout_ms: 60000
```

## 相关文档

- [资源管理概述](./README.md)
- [租约管理](./lease-manager.md)
- [资源池](./resource-pool.md)
