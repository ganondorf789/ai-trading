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
  addToast,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { userManagementApi, User } from "@/services/api";
import { formatTime } from "@/utils";

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

export default function UsersPage() {
  // 数据状态
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [activeFilter, setActiveFilter] = useState<string>("");
  const [searchValue, setSearchValue] = useState("");

  // 编辑角色弹窗
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [newRole, setNewRole] = useState<string>("");
  const [updating, setUpdating] = useState(false);

  // 加载用户列表
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        limit: 100,
      };

      if (roleFilter) {
        params.role = roleFilter;
      }
      if (activeFilter) {
        params.is_active = activeFilter === "true";
      }

      const response = await userManagementApi.getUsers(params);

      if (response.success && response.data) {
        let filtered = response.data;

        // 本地搜索
        if (searchValue) {
          const search = searchValue.toLowerCase();
          filtered = filtered.filter(
            (u) =>
              u.account.toLowerCase().includes(search) ||
              u.api_wallet?.toLowerCase().includes(search) ||
              u.wallet_address?.toLowerCase().includes(search)
          );
        }

        setUsers(filtered);
      }
    } catch (error: any) {
      console.error("Failed to fetch users:", error);
      addToast({
        title: "错误",
        description: error.response?.data?.error || "加载用户列表失败",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [roleFilter, activeFilter, searchValue]);

  // 打开编辑角色弹窗
  const handleEditRole = (user: User) => {
    setSelectedUser(user);
    setNewRole(user.role);
    setEditModalOpen(true);
  };

  // 更新用户角色
  const handleUpdateRole = async () => {
    if (!selectedUser || !newRole) return;

    setUpdating(true);
    try {
      const response = await userManagementApi.updateUserRole(selectedUser.id, {
        role: newRole,
      });

      if (response.success) {
        addToast({
          title: "成功",
          description: "用户身份更新成功",
          color: "success",
        });
        setEditModalOpen(false);
        fetchUsers();
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

  // 初始加载
  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6">
        {/* 标题栏 */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Icon icon="lucide:users" width={28} />
            用户管理
          </h1>
        </div>

        {/* 筛选栏 */}
        <div className="flex flex-wrap gap-4 items-center">
          <Input
            placeholder="搜索账号/钱包地址..."
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
            placeholder="状态"
            selectedKeys={activeFilter ? [activeFilter] : []}
            onSelectionChange={(keys) => setActiveFilter(Array.from(keys)[0] as string || "")}
            className="w-32"
          >
            <SelectItem key="">全部</SelectItem>
            <SelectItem key="true">活跃</SelectItem>
            <SelectItem key="false">禁用</SelectItem>
          </Select>

          <Button
            color="primary"
            variant="flat"
            startContent={<Icon icon="lucide:refresh-cw" />}
            onPress={() => fetchUsers()}
            isLoading={loading}
          >
            刷新
          </Button>
        </div>

        {/* 用户表格 */}
        <Table aria-label="用户列表">
          <TableHeader>
            <TableColumn>ID</TableColumn>
            <TableColumn>账号</TableColumn>
            <TableColumn>身份</TableColumn>
            <TableColumn>状态</TableColumn>
            <TableColumn>API钱包</TableColumn>
            <TableColumn>钱包地址</TableColumn>
            <TableColumn>过期时间</TableColumn>
            <TableColumn>注册时间</TableColumn>
            <TableColumn>最后登录</TableColumn>
            <TableColumn>操作</TableColumn>
          </TableHeader>
          <TableBody
            items={users}
            isLoading={loading}
            loadingContent={<Spinner label="加载中..." />}
            emptyContent="暂无用户数据"
          >
            {(user) => (
              <TableRow key={user.id}>
                <TableCell>{user.id}</TableCell>
                <TableCell>
                  <span className="font-medium">{user.account}</span>
                </TableCell>
                <TableCell>
                  <Chip color={roleColorMap[user.role]} size="sm" variant="flat">
                    {roleNameMap[user.role] || user.role}
                  </Chip>
                </TableCell>
                <TableCell>
                  <Chip
                    color={user.is_active ? "success" : "default"}
                    size="sm"
                    variant="dot"
                  >
                    {user.is_active ? "活跃" : "禁用"}
                  </Chip>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-xs">
                    {user.api_wallet ? `${user.api_wallet.slice(0, 6)}...${user.api_wallet.slice(-4)}` : "-"}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-xs">
                    {user.wallet_address ? `${user.wallet_address.slice(0, 6)}...${user.wallet_address.slice(-4)}` : "-"}
                  </span>
                </TableCell>
                <TableCell>
                  {user.expires_at ? (
                    <span className={new Date(user.expires_at) < new Date() ? "text-danger" : ""}>
                      {formatTime(user.expires_at)}
                    </span>
                  ) : (
                    <span className="text-success">永久</span>
                  )}
                </TableCell>
                <TableCell>{formatTime(user.created_at)}</TableCell>
                <TableCell>
                  {user.last_login_at ? formatTime(user.last_login_at) : "-"}
                </TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    variant="flat"
                    startContent={<Icon icon="lucide:edit" />}
                    onPress={() => handleEditRole(user)}
                  >
                    编辑身份
                  </Button>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        {/* 编辑角色弹窗 */}
        <Modal isOpen={editModalOpen} onClose={() => setEditModalOpen(false)}>
          <ModalContent>
            <ModalHeader>编辑用户身份</ModalHeader>
            <ModalBody>
              {selectedUser && (
                <div className="flex flex-col gap-4">
                  <div>
                    <p className="text-default-500 text-sm">账号</p>
                    <p className="font-medium">{selectedUser.account}</p>
                  </div>
                  <Select
                    label="用户身份"
                    selectedKeys={[newRole]}
                    onSelectionChange={(keys) => setNewRole(Array.from(keys)[0] as string)}
                  >
                    <SelectItem key="user">普通用户</SelectItem>
                    <SelectItem key="member">会员</SelectItem>
                    <SelectItem key="admin">管理员</SelectItem>
                  </Select>
                </div>
              )}
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setEditModalOpen(false)}>
                取消
              </Button>
              <Button color="primary" onPress={handleUpdateRole} isLoading={updating}>
                保存
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </div>
    </DefaultLayout>
  );
}
