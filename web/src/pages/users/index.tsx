import { useState, useEffect, useCallback, useMemo } from "react";
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
import { DatePicker } from "@heroui/date-picker";
import { CalendarDateTime } from "@internationalized/date";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { userManagementApi, User } from "@/services/api";
import { formatTime } from "@/utils";
import { TablePagination, useLocalPagination } from "@/components/TablePagination";

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

  // 分页
  const {
    page,
    setPage,
    rowsPerPage,
    setRowsPerPage,
    totalPages,
    getPageItems,
  } = useLocalPagination({ totalItems: users.length, defaultRowsPerPage: 20 });

  // 当前页的用户数据
  const paginatedUsers = useMemo(() => getPageItems(users), [getPageItems, users]);

  // 编辑用户信息弹窗（身份、过期时间、IP、端口）
  const [editInfoModalOpen, setEditInfoModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [editRole, setEditRole] = useState<string>("");
  const [editExpiresAt, setEditExpiresAt] = useState<CalendarDateTime | null>(null);
  const [editAllowedIp, setEditAllowedIp] = useState<string>("");
  const [editAllowedPort, setEditAllowedPort] = useState<string>("");
  const [updatingInfo, setUpdatingInfo] = useState(false);

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

  // 打开编辑信息弹窗
  const handleEditInfo = (user: User) => {
    setSelectedUser(user);
    setEditRole(user.role);
    // 转换过期时间为 CalendarDateTime
    if (user.expires_at) {
      try {
        const d = new Date(user.expires_at);
        setEditExpiresAt(
          new CalendarDateTime(
            d.getFullYear(),
            d.getMonth() + 1,
            d.getDate(),
            d.getHours(),
            d.getMinutes()
          )
        );
      } catch {
        setEditExpiresAt(null);
      }
    } else {
      setEditExpiresAt(null);
    }
    setEditAllowedIp(user.allowed_ip || "");
    setEditAllowedPort(user.allowed_port || "");
    setEditInfoModalOpen(true);
  };

  // 更新用户信息
  const handleUpdateInfo = async () => {
    if (!selectedUser) return;

    setUpdatingInfo(true);
    try {
      const updateData: { role?: string; expires_at?: string; allowed_ip?: string; allowed_port?: string } = {
        role: editRole,
        allowed_ip: editAllowedIp,
        allowed_port: editAllowedPort,
      };

      if (editExpiresAt) {
        const d = new Date(
          editExpiresAt.year,
          editExpiresAt.month - 1,
          editExpiresAt.day,
          editExpiresAt.hour,
          editExpiresAt.minute
        );
        updateData.expires_at = d.toISOString();
      } else {
        updateData.expires_at = "none";
      }

      const response = await userManagementApi.updateUserInfo(selectedUser.id, updateData);

      if (response.success) {
        addToast({
          title: "成功",
          description: "用户信息更新成功",
          color: "success",
        });
        setEditInfoModalOpen(false);
        fetchUsers();
      }
    } catch (error: any) {
      addToast({
        title: "错误",
        description: error.response?.data?.error || "更新失败",
        color: "danger",
      });
    } finally {
      setUpdatingInfo(false);
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
        <Table 
          aria-label="用户列表"
          bottomContent={
            totalPages > 1 ? (
              <TablePagination
                page={page}
                totalPages={totalPages}
                totalCount={users.length}
                rowsPerPage={rowsPerPage}
                onPageChange={setPage}
                onRowsPerPageChange={setRowsPerPage}
              />
            ) : null
          }
          bottomContentPlacement="outside"
        >
          <TableHeader>
            <TableColumn>ID</TableColumn>
            <TableColumn>账号</TableColumn>
            <TableColumn>身份</TableColumn>
            <TableColumn>状态</TableColumn>
            <TableColumn>IP</TableColumn>
            <TableColumn>端口</TableColumn>
            <TableColumn>过期时间</TableColumn>
            <TableColumn>注册时间</TableColumn>
            <TableColumn>最后登录</TableColumn>
            <TableColumn>操作</TableColumn>
          </TableHeader>
          <TableBody
            items={paginatedUsers}
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
                    {user.allowed_ip || "-"}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-xs">
                    {user.allowed_port || "-"}
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
                    onPress={() => handleEditInfo(user)}
                  >
                    编辑
                  </Button>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        {/* 编辑用户信息弹窗 */}
        <Modal isOpen={editInfoModalOpen} onClose={() => setEditInfoModalOpen(false)}>
          <ModalContent>
            <ModalHeader>编辑用户信息</ModalHeader>
            <ModalBody>
              {selectedUser && (
                <div className="flex flex-col gap-4">
                  <div>
                    <p className="text-default-500 text-sm">账号</p>
                    <p className="font-medium">{selectedUser.account}</p>
                  </div>
                  <Select
                    label="用户身份"
                    selectedKeys={[editRole]}
                    onSelectionChange={(keys) => setEditRole(Array.from(keys)[0] as string)}
                  >
                    <SelectItem key="user">普通用户</SelectItem>
                    <SelectItem key="member">会员</SelectItem>
                    <SelectItem key="admin">管理员</SelectItem>
                  </Select>
                  <DatePicker
                    label="过期时间"
                    granularity="minute"
                    value={editExpiresAt as any}
                    onChange={(v: any) => setEditExpiresAt(v)}
                    description="留空表示永不过期"
                    showMonthAndYearPickers
                    hourCycle={24}
                  />
                  {editExpiresAt && (
                    <Button
                      size="sm"
                      variant="light"
                      color="danger"
                      startContent={<Icon icon="lucide:x" />}
                      onPress={() => setEditExpiresAt(null)}
                    >
                      清除过期时间（设为永久）
                    </Button>
                  )}
                  <Input
                    label="IP 地址"
                    placeholder="例如: 192.168.1.1"
                    value={editAllowedIp}
                    onValueChange={setEditAllowedIp}
                    isClearable
                    onClear={() => setEditAllowedIp("")}
                  />
                  <Input
                    label="端口"
                    placeholder="例如: 8080"
                    value={editAllowedPort}
                    onValueChange={setEditAllowedPort}
                    isClearable
                    onClear={() => setEditAllowedPort("")}
                  />
                </div>
              )}
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setEditInfoModalOpen(false)}>
                取消
              </Button>
              <Button color="primary" onPress={handleUpdateInfo} isLoading={updatingInfo}>
                保存
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </div>
    </DefaultLayout>
  );
}
