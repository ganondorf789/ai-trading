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
  Switch,
  Textarea,
  addToast,
  Card,
  CardBody,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { appVersionApi, AppVersion, AppVersionStats } from "@/services/api";
import { formatTime } from "@/utils";

const platformColorMap: Record<string, "default" | "primary" | "success" | "warning" | "danger"> = {
  all: "primary",
  android: "success",
  ios: "warning",
  web: "default",
};

const platformNameMap: Record<string, string> = {
  all: "全平台",
  android: "Android",
  ios: "iOS",
  web: "Web",
};

export default function AppVersionsPage() {
  // 数据状态
  const [versions, setVersions] = useState<AppVersion[]>([]);
  const [stats, setStats] = useState<AppVersionStats | null>(null);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [visibleFilter, setVisibleFilter] = useState<string>("");
  const [platformFilter, setPlatformFilter] = useState<string>("");

  // 创建/编辑弹窗
  const [modalOpen, setModalOpen] = useState(false);
  const [editingVersion, setEditingVersion] = useState<AppVersion | null>(null);
  const [formData, setFormData] = useState({
    version: "",
    version_name: "",
    description: "",
    release_notes: "",
    download_url: "",
    is_force_update: false,
    is_visible: true,
    min_supported_version: "",
    platform: "all",
  });
  const [saving, setSaving] = useState(false);

  // 删除确认弹窗
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingVersion, setDeletingVersion] = useState<AppVersion | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 加载版本列表
  const fetchVersions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        limit: 100,
      };

      if (visibleFilter) {
        params.is_visible = visibleFilter === "true";
      }
      if (platformFilter) {
        params.platform = platformFilter;
      }

      const response = await appVersionApi.getVersions(params);

      if (response.success && response.data) {
        setVersions(response.data);
      }
    } catch (error: any) {
      console.error("Failed to fetch versions:", error);
      addToast({
        title: "错误",
        description: error.response?.data?.error || "加载版本列表失败",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [visibleFilter, platformFilter]);

  // 加载统计信息
  const fetchStats = useCallback(async () => {
    try {
      const response = await appVersionApi.getVersionStats();
      if (response.success && response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    }
  }, []);

  // 打开创建弹窗
  const handleCreate = () => {
    setEditingVersion(null);
    setFormData({
      version: "",
      version_name: "",
      description: "",
      release_notes: "",
      download_url: "",
      is_force_update: false,
      is_visible: true,
      min_supported_version: "",
      platform: "all",
    });
    setModalOpen(true);
  };

  // 打开编辑弹窗
  const handleEdit = (version: AppVersion) => {
    setEditingVersion(version);
    setFormData({
      version: version.version,
      version_name: version.version_name || "",
      description: version.description || "",
      release_notes: version.release_notes || "",
      download_url: version.download_url || "",
      is_force_update: version.is_force_update,
      is_visible: version.is_visible,
      min_supported_version: version.min_supported_version || "",
      platform: version.platform,
    });
    setModalOpen(true);
  };

  // 保存版本
  const handleSave = async () => {
    if (!formData.version.trim()) {
      addToast({
        title: "错误",
        description: "版本号不能为空",
        color: "danger",
      });
      return;
    }

    setSaving(true);
    try {
      if (editingVersion) {
        // 更新
        const response = await appVersionApi.updateVersion(editingVersion.id, {
          version_name: formData.version_name,
          description: formData.description,
          release_notes: formData.release_notes,
          download_url: formData.download_url,
          is_force_update: formData.is_force_update,
          is_visible: formData.is_visible,
          min_supported_version: formData.min_supported_version,
        });

        if (response.success) {
          addToast({
            title: "成功",
            description: "版本更新成功",
            color: "success",
          });
          setModalOpen(false);
          fetchVersions();
          fetchStats();
        }
      } else {
        // 创建
        const response = await appVersionApi.createVersion(formData);

        if (response.success) {
          addToast({
            title: "成功",
            description: "版本创建成功",
            color: "success",
          });
          setModalOpen(false);
          fetchVersions();
          fetchStats();
        }
      }
    } catch (error: any) {
      addToast({
        title: "错误",
        description: error.response?.data?.error || "操作失败",
        color: "danger",
      });
    } finally {
      setSaving(false);
    }
  };

  // 切换可见性
  const handleToggleVisibility = async (version: AppVersion) => {
    try {
      const response = await appVersionApi.toggleVisibility(version.id, !version.is_visible);

      if (response.success) {
        addToast({
          title: "成功",
          description: `版本已${!version.is_visible ? "显示" : "隐藏"}`,
          color: "success",
        });
        fetchVersions();
        fetchStats();
      }
    } catch (error: any) {
      addToast({
        title: "错误",
        description: error.response?.data?.error || "操作失败",
        color: "danger",
      });
    }
  };

  // 打开删除确认
  const handleDeleteClick = (version: AppVersion) => {
    setDeletingVersion(version);
    setDeleteModalOpen(true);
  };

  // 确认删除
  const handleDelete = async () => {
    if (!deletingVersion) return;

    setDeleting(true);
    try {
      const response = await appVersionApi.deleteVersion(deletingVersion.id);

      if (response.success) {
        addToast({
          title: "成功",
          description: "版本删除成功",
          color: "success",
        });
        setDeleteModalOpen(false);
        fetchVersions();
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

  // 初始加载
  useEffect(() => {
    fetchVersions();
    fetchStats();
  }, [fetchVersions, fetchStats]);

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6">
        {/* 标题栏 */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Icon icon="lucide:package" width={28} />
            版本管理
          </h1>
          <p className="text-default-500 mt-1">
            管理应用版本，控制版本可见性
          </p>
        </div>

        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardBody className="py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Icon icon="lucide:layers" className="text-primary" width={20} />
                  </div>
                  <div>
                    <p className="text-xs text-default-500">总版本数</p>
                    <p className="text-lg font-bold">{stats.total_count}</p>
                  </div>
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-success/10 rounded-lg">
                    <Icon icon="lucide:eye" className="text-success" width={20} />
                  </div>
                  <div>
                    <p className="text-xs text-default-500">可见版本</p>
                    <p className="text-lg font-bold">{stats.visible_count}</p>
                  </div>
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-default/10 rounded-lg">
                    <Icon icon="lucide:eye-off" className="text-default-500" width={20} />
                  </div>
                  <div>
                    <p className="text-xs text-default-500">隐藏版本</p>
                    <p className="text-lg font-bold">{stats.hidden_count}</p>
                  </div>
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-danger/10 rounded-lg">
                    <Icon icon="lucide:alert-triangle" className="text-danger" width={20} />
                  </div>
                  <div>
                    <p className="text-xs text-default-500">强制更新</p>
                    <p className="text-lg font-bold">{stats.force_update_count}</p>
                  </div>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 筛选栏 */}
        <div className="flex flex-wrap gap-4 items-center">
          <Select
            placeholder="可见性"
            selectedKeys={visibleFilter ? [visibleFilter] : []}
            onSelectionChange={(keys) => setVisibleFilter(Array.from(keys)[0] as string || "")}
            className="w-32"
          >
            <SelectItem key="">全部</SelectItem>
            <SelectItem key="true">可见</SelectItem>
            <SelectItem key="false">隐藏</SelectItem>
          </Select>

          <Select
            placeholder="平台"
            selectedKeys={platformFilter ? [platformFilter] : []}
            onSelectionChange={(keys) => setPlatformFilter(Array.from(keys)[0] as string || "")}
            className="w-32"
          >
            <SelectItem key="">全部</SelectItem>
            <SelectItem key="all">全平台</SelectItem>
            <SelectItem key="android">Android</SelectItem>
            <SelectItem key="ios">iOS</SelectItem>
            <SelectItem key="web">Web</SelectItem>
          </Select>

          <Button
            color="primary"
            variant="flat"
            startContent={<Icon icon="lucide:refresh-cw" />}
            onPress={() => {
              fetchVersions();
              fetchStats();
            }}
            isLoading={loading}
          >
            刷新
          </Button>

          <div className="flex-1" />

          <Button
            color="primary"
            startContent={<Icon icon="lucide:plus" />}
            onPress={handleCreate}
          >
            创建版本
          </Button>
        </div>

        {/* 版本表格 */}
        <Table aria-label="版本列表">
          <TableHeader>
            <TableColumn>版本号</TableColumn>
            <TableColumn>版本名称</TableColumn>
            <TableColumn>平台</TableColumn>
            <TableColumn>可见性</TableColumn>
            <TableColumn>强制更新</TableColumn>
            <TableColumn>描述</TableColumn>
            <TableColumn>创建时间</TableColumn>
            <TableColumn>操作</TableColumn>
          </TableHeader>
          <TableBody
            items={versions}
            isLoading={loading}
            loadingContent={<Spinner label="加载中..." />}
            emptyContent="暂无版本数据"
          >
            {(version) => (
              <TableRow key={version.id}>
                <TableCell>
                  <span className="font-mono font-medium">{version.version}</span>
                </TableCell>
                <TableCell>
                  <span className="text-default-500">{version.version_name || "-"}</span>
                </TableCell>
                <TableCell>
                  <Chip color={platformColorMap[version.platform]} size="sm" variant="flat">
                    {platformNameMap[version.platform] || version.platform}
                  </Chip>
                </TableCell>
                <TableCell>
                  <Switch
                    size="sm"
                    isSelected={version.is_visible}
                    onValueChange={() => handleToggleVisibility(version)}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    color={version.is_force_update ? "danger" : "default"}
                    size="sm"
                    variant="dot"
                  >
                    {version.is_force_update ? "是" : "否"}
                  </Chip>
                </TableCell>
                <TableCell>
                  <span className="text-default-500 text-sm line-clamp-1 max-w-[200px]">
                    {version.description || "-"}
                  </span>
                </TableCell>
                <TableCell>{formatTime(version.created_at)}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="flat"
                      isIconOnly
                      onPress={() => handleEdit(version)}
                    >
                      <Icon icon="lucide:edit" />
                    </Button>
                    <Button
                      size="sm"
                      variant="flat"
                      color="danger"
                      isIconOnly
                      onPress={() => handleDeleteClick(version)}
                    >
                      <Icon icon="lucide:trash-2" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        {/* 创建/编辑弹窗 */}
        <Modal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          size="2xl"
          scrollBehavior="inside"
        >
          <ModalContent>
            <ModalHeader>
              {editingVersion ? "编辑版本" : "创建版本"}
            </ModalHeader>
            <ModalBody>
              <div className="flex flex-col gap-4">
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="版本号"
                    placeholder="如 1.0.0"
                    value={formData.version}
                    onValueChange={(value) => setFormData({ ...formData, version: value })}
                    isRequired
                    isDisabled={!!editingVersion}
                  />
                  <Input
                    label="版本名称"
                    placeholder="可选，如 正式版"
                    value={formData.version_name}
                    onValueChange={(value) => setFormData({ ...formData, version_name: value })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <Select
                    label="平台"
                    selectedKeys={[formData.platform]}
                    onSelectionChange={(keys) => setFormData({ ...formData, platform: Array.from(keys)[0] as string })}
                    isDisabled={!!editingVersion}
                  >
                    <SelectItem key="all">全平台</SelectItem>
                    <SelectItem key="android">Android</SelectItem>
                    <SelectItem key="ios">iOS</SelectItem>
                    <SelectItem key="web">Web</SelectItem>
                  </Select>
                  <Input
                    label="最低支持版本"
                    placeholder="可选，如 1.0.0"
                    value={formData.min_supported_version}
                    onValueChange={(value) => setFormData({ ...formData, min_supported_version: value })}
                  />
                </div>

                <Input
                  label="下载链接"
                  placeholder="可选，版本下载地址"
                  value={formData.download_url}
                  onValueChange={(value) => setFormData({ ...formData, download_url: value })}
                />

                <Textarea
                  label="版本描述"
                  placeholder="简短描述此版本"
                  value={formData.description}
                  onValueChange={(value) => setFormData({ ...formData, description: value })}
                  minRows={2}
                />

                <Textarea
                  label="更新日志"
                  placeholder="详细的更新内容说明"
                  value={formData.release_notes}
                  onValueChange={(value) => setFormData({ ...formData, release_notes: value })}
                  minRows={4}
                />

                <div className="flex gap-6">
                  <Switch
                    isSelected={formData.is_visible}
                    onValueChange={(value) => setFormData({ ...formData, is_visible: value })}
                  >
                    对用户可见
                  </Switch>
                  <Switch
                    isSelected={formData.is_force_update}
                    onValueChange={(value) => setFormData({ ...formData, is_force_update: value })}
                    color="danger"
                  >
                    强制更新
                  </Switch>
                </div>
              </div>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setModalOpen(false)}>
                取消
              </Button>
              <Button color="primary" onPress={handleSave} isLoading={saving}>
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
              <p>
                确定要删除版本 <strong>{deletingVersion?.version}</strong> 吗？此操作不可恢复。
              </p>
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
