import { useState, useEffect, useCallback } from "react";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Chip,
  Spinner,
  Select,
  SelectItem,
  Input,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Card,
  CardBody,
  Tooltip,
  addToast,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { secretKeyApi, SecretKey, SecretKeyStats } from "@/services/api";
import { formatTime } from "@/utils";

// 临时使用固定的管理员ID，实际应从登录状态获取
const ADMIN_USER_ID = 1;

const roleColorMap: Record<string, "default" | "primary" | "success" | "warning" | "danger"> = {
  user: "default",
  member: "primary",
  admin: "danger",
};

const roleNameMap: Record<string, string> = {
  user: "普通用户",
  member: "会员",
  admin: "管理员",
};

export default function SecretKeysPage() {
  // 数据状态
  const [keys, setKeys] = useState<SecretKey[]>([]);
  const [stats, setStats] = useState<SecretKeyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);

  // 筛选状态
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [usedFilter, setUsedFilter] = useState<string>("");
  const [activeFilter, setActiveFilter] = useState<string>("");
  const [searchValue, setSearchValue] = useState("");

  // 创建秘钥弹窗
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    key_name: "",
    user_role: "user",
    expires_days: 30,
    count: 1,
  });
  const [creating, setCreating] = useState(false);

  // 编辑秘钥弹窗
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<SecretKey | null>(null);
  const [editForm, setEditForm] = useState({
    key_name: "",
    user_role: "user",
    expires_days: 30,
    is_active: true,
  });
  const [updating, setUpdating] = useState(false);

  // 删除确认弹窗
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [keyToDelete, setKeyToDelete] = useState<SecretKey | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 加载秘钥列表
  const fetchKeys = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        user_id: ADMIN_USER_ID,
        limit: 100,
      };

      if (roleFilter) {
        params.user_role = roleFilter;
      }
      if (usedFilter) {
        params.is_used = usedFilter === "true";
      }
      if (activeFilter) {
        params.is_active = activeFilter === "true";
      }

      const response = await secretKeyApi.getSecretKeys(params);

      if (response.success && response.data) {
        let filtered = response.data;

        // 本地搜索
        if (searchValue) {
          const search = searchValue.toLowerCase();
          filtered = filtered.filter(
            (k) =>
              k.key_value.toLowerCase().includes(search) ||
              k.key_name?.toLowerCase().includes(search)
          );
        }

        setKeys(filtered);
      }
    } catch (error: any) {
      console.error("Failed to fetch keys:", error);
      addToast({
        title: "错误",
        description: error.response?.data?.error || "加载秘钥列表失败",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [roleFilter, usedFilter, activeFilter, searchValue]);

  // 加载统计数据
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const response = await secretKeyApi.getSecretKeyStats(ADMIN_USER_ID);
      if (response.success && response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // 创建秘钥
  const handleCreate = async () => {
    setCreating(true);
    try {
      if (createForm.count > 1) {
        // 批量创建
        const response = await secretKeyApi.batchCreateSecretKeys({
          user_id: ADMIN_USER_ID,
          count: createForm.count,
          key_name_prefix: createForm.key_name,
          user_role: createForm.user_role,
          expires_days: createForm.expires_days,
        });

        if (response.success) {
          addToast({
            title: "成功",
            description: response.message || `成功创建 ${response.data?.length} 个秘钥`,
            color: "success",
          });
          setCreateModalOpen(false);
          setCreateForm({ key_name: "", user_role: "user", expires_days: 30, count: 1 });
          fetchKeys();
          fetchStats();
        }
      } else {
        // 单个创建
        const response = await secretKeyApi.createSecretKey({
          user_id: ADMIN_USER_ID,
          key_name: createForm.key_name,
          user_role: createForm.user_role,
          expires_days: createForm.expires_days,
        });

        if (response.success) {
          addToast({
            title: "成功",
            description: "秘钥创建成功",
            color: "success",
          });
          setCreateModalOpen(false);
          setCreateForm({ key_name: "", user_role: "user", expires_days: 30, count: 1 });
          fetchKeys();
          fetchStats();
        }
      }
    } catch (error: any) {
      addToast({
        title: "错误",
        description: error.response?.data?.error || "创建失败",
        color: "danger",
      });
    } finally {
      setCreating(false);
    }
  };

  // 打开编辑弹窗
  const handleEdit = (key: SecretKey) => {
    setSelectedKey(key);
    setEditForm({
      key_name: key.key_name || "",
      user_role: key.user_role,
      expires_days: key.expires_days,
      is_active: key.is_active,
    });
    setEditModalOpen(true);
  };

  // 更新秘钥
  const handleUpdate = async () => {
    if (!selectedKey) return;

    setUpdating(true);
    try {
      const response = await secretKeyApi.updateSecretKey(selectedKey.id, {
        user_id: ADMIN_USER_ID,
        key_name: editForm.key_name,
        user_role: editForm.user_role,
        expires_days: editForm.expires_days,
        is_active: editForm.is_active,
      });

      if (response.success) {
        addToast({
          title: "成功",
          description: "秘钥更新成功",
          color: "success",
        });
        setEditModalOpen(false);
        fetchKeys();
        fetchStats();
      }
    } catch (error: any) {
      addToast({
        title: "错误",
        description: error.response?.data?.error || "更新失败",
        color: "danger",
      });
    } finally {
      setUpdating(false);
    }
  };

  // 打开删除确认
  const handleDeleteClick = (key: SecretKey) => {
    setKeyToDelete(key);
    setDeleteModalOpen(true);
  };

  // 删除秘钥
  const handleDelete = async () => {
    if (!keyToDelete) return;

    setDeleting(true);
    try {
      const response = await secretKeyApi.deleteSecretKey(keyToDelete.id, ADMIN_USER_ID);

      if (response.success) {
        addToast({
          title: "成功",
          description: "秘钥已删除",
          color: "success",
        });
        setDeleteModalOpen(false);
        setKeyToDelete(null);
        fetchKeys();
        fetchStats();
      }
    } catch (error: any) {
      addToast({
        title: "错误",
        description: error.response?.data?.error || "删除失败",
        color: "danger",
      });
    } finally {
      setDeleting(false);
    }
  };

  // 复制秘钥
  const handleCopy = (keyValue: string) => {
    navigator.clipboard.writeText(keyValue);
    addToast({
      title: "已复制",
      description: "秘钥已复制到剪贴板",
      color: "success",
    });
  };

  // 初始加载
  useEffect(() => {
    fetchKeys();
    fetchStats();
  }, [fetchKeys, fetchStats]);

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6">
        {/* 标题栏 */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Icon icon="lucide:key" width={28} />
              秘钥管理
            </h1>
            <p className="text-default-500 mt-1">
              管理注册秘钥，每个秘钥只能使用一次
            </p>
          </div>
          <Button
            color="primary"
            startContent={<Icon icon="lucide:plus" />}
            onPress={() => setCreateModalOpen(true)}
          >
            创建秘钥
          </Button>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">总数</p>
              <p className="text-2xl font-bold">
                {statsLoading ? <Spinner size="sm" /> : stats?.total_count || 0}
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">可用</p>
              <p className="text-2xl font-bold text-success">
                {statsLoading ? <Spinner size="sm" /> : stats?.available_count || 0}
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">已使用</p>
              <p className="text-2xl font-bold text-warning">
                {statsLoading ? <Spinner size="sm" /> : stats?.used_count || 0}
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">已启用</p>
              <p className="text-2xl font-bold text-primary">
                {statsLoading ? <Spinner size="sm" /> : stats?.active_count || 0}
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">已禁用</p>
              <p className="text-2xl font-bold text-default-400">
                {statsLoading ? <Spinner size="sm" /> : stats?.inactive_count || 0}
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">普通用户</p>
              <p className="text-2xl font-bold">
                {statsLoading ? <Spinner size="sm" /> : stats?.user_role_count || 0}
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">会员</p>
              <p className="text-2xl font-bold text-primary">
                {statsLoading ? <Spinner size="sm" /> : stats?.member_role_count || 0}
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-default-500 text-sm">管理员</p>
              <p className="text-2xl font-bold text-danger">
                {statsLoading ? <Spinner size="sm" /> : stats?.admin_role_count || 0}
              </p>
            </CardBody>
          </Card>
        </div>

        {/* 筛选栏 */}
        <div className="flex flex-wrap gap-4 items-center">
          <Input
            placeholder="搜索秘钥/名称..."
            value={searchValue}
            onValueChange={setSearchValue}
            startContent={<Icon icon="lucide:search" className="text-default-400" />}
            className="w-64"
            isClearable
            onClear={() => setSearchValue("")}
          />

          <Select
            placeholder="用户身份"
            selectedKeys={roleFilter ? [roleFilter] : []}
            onSelectionChange={(keys) => setRoleFilter(Array.from(keys)[0] as string || "")}
            className="w-32"
          >
            <SelectItem key="">全部</SelectItem>
            <SelectItem key="user">普通用户</SelectItem>
            <SelectItem key="member">会员</SelectItem>
            <SelectItem key="admin">管理员</SelectItem>
          </Select>

          <Select
            placeholder="使用状态"
            selectedKeys={usedFilter ? [usedFilter] : []}
            onSelectionChange={(keys) => setUsedFilter(Array.from(keys)[0] as string || "")}
            className="w-32"
          >
            <SelectItem key="">全部</SelectItem>
            <SelectItem key="false">未使用</SelectItem>
            <SelectItem key="true">已使用</SelectItem>
          </Select>

          <Select
            placeholder="启用状态"
            selectedKeys={activeFilter ? [activeFilter] : []}
            onSelectionChange={(keys) => setActiveFilter(Array.from(keys)[0] as string || "")}
            className="w-32"
          >
            <SelectItem key="">全部</SelectItem>
            <SelectItem key="true">已启用</SelectItem>
            <SelectItem key="false">已禁用</SelectItem>
          </Select>

          <Button
            color="primary"
            variant="flat"
            startContent={<Icon icon="lucide:refresh-cw" />}
            onPress={() => {
              fetchKeys();
              fetchStats();
            }}
            isLoading={loading}
          >
            刷新
          </Button>
        </div>

        {/* 秘钥表格 */}
        <Table aria-label="秘钥列表">
          <TableHeader>
            <TableColumn>ID</TableColumn>
            <TableColumn>秘钥</TableColumn>
            <TableColumn>名称</TableColumn>
            <TableColumn>用户身份</TableColumn>
            <TableColumn>有效期(天)</TableColumn>
            <TableColumn>状态</TableColumn>
            <TableColumn>使用者ID</TableColumn>
            <TableColumn>创建时间</TableColumn>
            <TableColumn>操作</TableColumn>
          </TableHeader>
          <TableBody
            items={keys}
            isLoading={loading}
            loadingContent={<Spinner label="加载中..." />}
            emptyContent="暂无秘钥数据"
          >
            {(key) => (
              <TableRow key={key.id}>
                <TableCell>{key.id}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <code className="text-xs bg-default-100 px-2 py-1 rounded font-mono">
                      {key.key_value.slice(0, 8)}...{key.key_value.slice(-4)}
                    </code>
                    <Tooltip content="复制秘钥">
                      <Button
                        size="sm"
                        variant="light"
                        isIconOnly
                        onPress={() => handleCopy(key.key_value)}
                      >
                        <Icon icon="lucide:copy" width={16} />
                      </Button>
                    </Tooltip>
                  </div>
                </TableCell>
                <TableCell>{key.key_name || "-"}</TableCell>
                <TableCell>
                  <Chip color={roleColorMap[key.user_role]} size="sm" variant="flat">
                    {roleNameMap[key.user_role] || key.user_role}
                  </Chip>
                </TableCell>
                <TableCell>
                  {key.expires_days === 0 ? (
                    <span className="text-success">永久</span>
                  ) : (
                    key.expires_days
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Chip
                      color={key.is_active ? "success" : "default"}
                      size="sm"
                      variant="dot"
                    >
                      {key.is_active ? "启用" : "禁用"}
                    </Chip>
                    <Chip
                      color={key.is_used ? "warning" : "primary"}
                      size="sm"
                      variant="flat"
                    >
                      {key.is_used ? "已使用" : "未使用"}
                    </Chip>
                  </div>
                </TableCell>
                <TableCell>
                  {key.used_by_user_id || "-"}
                </TableCell>
                <TableCell>{formatTime(key.created_at)}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="flat"
                      isIconOnly
                      onPress={() => handleEdit(key)}
                    >
                      <Icon icon="lucide:edit" width={16} />
                    </Button>
                    <Button
                      size="sm"
                      variant="flat"
                      color="danger"
                      isIconOnly
                      onPress={() => handleDeleteClick(key)}
                    >
                      <Icon icon="lucide:trash-2" width={16} />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        {/* 创建秘钥弹窗 */}
        <Modal isOpen={createModalOpen} onClose={() => setCreateModalOpen(false)}>
          <ModalContent>
            <ModalHeader>创建秘钥</ModalHeader>
            <ModalBody>
              <div className="flex flex-col gap-4">
                <Input
                  label="秘钥名称/备注"
                  placeholder="输入名称便于识别"
                  value={createForm.key_name}
                  onValueChange={(v) => setCreateForm({ ...createForm, key_name: v })}
                />
                <Select
                  label="用户身份"
                  selectedKeys={[createForm.user_role]}
                  onSelectionChange={(keys) =>
                    setCreateForm({ ...createForm, user_role: Array.from(keys)[0] as string })
                  }
                >
                  <SelectItem key="user">普通用户</SelectItem>
                  <SelectItem key="member">会员</SelectItem>
                  <SelectItem key="admin">管理员</SelectItem>
                </Select>
                <Input
                  type="number"
                  label="用户有效期(天)"
                  description="0 表示永不过期"
                  value={String(createForm.expires_days)}
                  onValueChange={(v) =>
                    setCreateForm({ ...createForm, expires_days: parseInt(v) || 0 })
                  }
                />
                <Input
                  type="number"
                  label="创建数量"
                  description="批量创建多个秘钥"
                  min={1}
                  max={100}
                  value={String(createForm.count)}
                  onValueChange={(v) =>
                    setCreateForm({ ...createForm, count: Math.min(100, Math.max(1, parseInt(v) || 1)) })
                  }
                />
              </div>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setCreateModalOpen(false)}>
                取消
              </Button>
              <Button color="primary" onPress={handleCreate} isLoading={creating}>
                创建
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* 编辑秘钥弹窗 */}
        <Modal isOpen={editModalOpen} onClose={() => setEditModalOpen(false)}>
          <ModalContent>
            <ModalHeader>编辑秘钥</ModalHeader>
            <ModalBody>
              {selectedKey && (
                <div className="flex flex-col gap-4">
                  <div>
                    <p className="text-default-500 text-sm">秘钥值</p>
                    <code className="text-xs bg-default-100 px-2 py-1 rounded font-mono break-all">
                      {selectedKey.key_value}
                    </code>
                  </div>
                  <Input
                    label="秘钥名称/备注"
                    value={editForm.key_name}
                    onValueChange={(v) => setEditForm({ ...editForm, key_name: v })}
                  />
                  <Select
                    label="用户身份"
                    selectedKeys={[editForm.user_role]}
                    onSelectionChange={(keys) =>
                      setEditForm({ ...editForm, user_role: Array.from(keys)[0] as string })
                    }
                    isDisabled={selectedKey.is_used}
                  >
                    <SelectItem key="user">普通用户</SelectItem>
                    <SelectItem key="member">会员</SelectItem>
                    <SelectItem key="admin">管理员</SelectItem>
                  </Select>
                  <Input
                    type="number"
                    label="用户有效期(天)"
                    value={String(editForm.expires_days)}
                    onValueChange={(v) =>
                      setEditForm({ ...editForm, expires_days: parseInt(v) || 0 })
                    }
                    isDisabled={selectedKey.is_used}
                  />
                  <Select
                    label="启用状态"
                    selectedKeys={[String(editForm.is_active)]}
                    onSelectionChange={(keys) =>
                      setEditForm({ ...editForm, is_active: Array.from(keys)[0] === "true" })
                    }
                  >
                    <SelectItem key="true">启用</SelectItem>
                    <SelectItem key="false">禁用</SelectItem>
                  </Select>
                </div>
              )}
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setEditModalOpen(false)}>
                取消
              </Button>
              <Button color="primary" onPress={handleUpdate} isLoading={updating}>
                保存
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* 删除确认弹窗 */}
        <Modal isOpen={deleteModalOpen} onClose={() => setDeleteModalOpen(false)}>
          <ModalContent>
            <ModalHeader>确认删除</ModalHeader>
            <ModalBody>
              <p>确定要删除这个秘钥吗？此操作不可恢复。</p>
              {keyToDelete && (
                <code className="text-xs bg-default-100 px-2 py-1 rounded font-mono break-all mt-2 block">
                  {keyToDelete.key_value}
                </code>
              )}
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setDeleteModalOpen(false)}>
                取消
              </Button>
              <Button color="danger" onPress={handleDelete} isLoading={deleting}>
                删除
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </div>
    </DefaultLayout>
  );
}
