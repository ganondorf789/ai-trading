import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Spinner,
  Input,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Textarea,
  addToast,
  Tabs,
  Tab,
  Card,
  CardBody,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import ReactMarkdown from "react-markdown";
import "github-markdown-css/github-markdown-light.css";

import DefaultLayout from "@/layouts/default";
import { announcementApi, Announcement } from "@/services/api";
import { formatTime } from "@/utils";
import { TablePagination, useLocalPagination } from "@/components/TablePagination";

export default function AnnouncementsPage() {
  // 数据状态
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);

  // 分页
  const {
    page,
    setPage,
    rowsPerPage,
    setRowsPerPage,
    totalPages,
    getPageItems,
  } = useLocalPagination({ totalItems: announcements.length, defaultRowsPerPage: 20 });

  // 当前页的公告数据
  const paginatedAnnouncements = useMemo(() => getPageItems(announcements), [getPageItems, announcements]);

  // 创建/编辑弹窗
  const [modalOpen, setModalOpen] = useState(false);
  const [editingAnnouncement, setEditingAnnouncement] = useState<Announcement | null>(null);
  const [formData, setFormData] = useState({
    title: "",
    content: "",
  });
  const [saving, setSaving] = useState(false);

  // 删除确认弹窗
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingAnnouncement, setDeletingAnnouncement] = useState<Announcement | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 预览弹窗
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewingAnnouncement, setPreviewingAnnouncement] = useState<Announcement | null>(null);

  // 编辑器预览选项卡
  const [editorTab, setEditorTab] = useState<string>("edit");

  // 加载公告列表
  const fetchAnnouncements = useCallback(async () => {
    setLoading(true);
    try {
      const response = await announcementApi.getList({ limit: 100 });

      if (response.success && response.data) {
        setAnnouncements(response.data);
      }
    } catch (error: any) {
      console.error("Failed to fetch announcements:", error);
      addToast({
        title: "错误",
        description: error.response?.data?.error || "加载公告列表失败",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  // 打开创建弹窗
  const handleCreate = () => {
    setEditingAnnouncement(null);
    setFormData({
      title: "",
      content: "",
    });
    setModalOpen(true);
  };

  // 打开编辑弹窗
  const handleEdit = (announcement: Announcement) => {
    setEditingAnnouncement(announcement);
    setFormData({
      title: announcement.title || "",
      content: announcement.content || "",
    });
    setModalOpen(true);
  };

  // 保存公告
  const handleSave = async () => {
    if (!formData.title.trim()) {
      addToast({
        title: "错误",
        description: "公告标题不能为空",
        color: "danger",
      });
      return;
    }

    if (!formData.content.trim()) {
      addToast({
        title: "错误",
        description: "公告内容不能为空",
        color: "danger",
      });
      return;
    }

    setSaving(true);
    try {
      if (editingAnnouncement) {
        // 更新
        const response = await announcementApi.update(editingAnnouncement.id, {
          title: formData.title,
          content: formData.content,
        });

        if (response.success) {
          addToast({
            title: "成功",
            description: "公告更新成功",
            color: "success",
          });
          setModalOpen(false);
          fetchAnnouncements();
        }
      } else {
        // 创建（发布公告）
        const response = await announcementApi.create({
          title: formData.title,
          content: formData.content,
        });

        if (response.success) {
          addToast({
            title: "成功",
            description: "公告发布成功，已推送给所有用户",
            color: "success",
          });
          setModalOpen(false);
          fetchAnnouncements();
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

  // 打开删除确认
  const handleDeleteClick = (announcement: Announcement) => {
    setDeletingAnnouncement(announcement);
    setDeleteModalOpen(true);
  };

  // 打开预览
  const handlePreview = (announcement: Announcement) => {
    setPreviewingAnnouncement(announcement);
    setPreviewModalOpen(true);
  };

  // 确认删除
  const handleDelete = async () => {
    if (!deletingAnnouncement) return;

    setDeleting(true);
    try {
      const response = await announcementApi.delete(deletingAnnouncement.id);

      if (response.success) {
        addToast({
          title: "成功",
          description: "公告删除成功",
          color: "success",
        });
        setDeleteModalOpen(false);
        fetchAnnouncements();
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
    fetchAnnouncements();
  }, [fetchAnnouncements]);

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6">
        {/* 标题栏 */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Icon icon="lucide:megaphone" width={28} />
            公告管理
          </h1>
          <p className="text-default-500 mt-1">
            发布系统公告，公告将实时推送给所有在线用户
          </p>
        </div>

        {/* 操作栏 */}
        <div className="flex flex-wrap gap-4 items-center">
          <Button
            color="primary"
            variant="flat"
            startContent={<Icon icon="lucide:refresh-cw" />}
            onPress={() => fetchAnnouncements()}
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
            发布公告
          </Button>
        </div>

        {/* 公告表格 */}
        <Table 
          aria-label="公告列表"
          bottomContent={
            totalPages > 1 ? (
              <TablePagination
                page={page}
                totalPages={totalPages}
                totalCount={announcements.length}
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
            <TableColumn>标题</TableColumn>
            <TableColumn>内容预览</TableColumn>
            <TableColumn>发布时间</TableColumn>
            <TableColumn>操作</TableColumn>
          </TableHeader>
          <TableBody
            items={paginatedAnnouncements}
            isLoading={loading}
            loadingContent={<Spinner label="加载中..." />}
            emptyContent="暂无公告数据"
          >
            {(announcement) => (
              <TableRow key={announcement.id}>
                <TableCell>
                  <span className="font-mono text-default-500">#{announcement.id}</span>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Icon icon="lucide:bell" className="text-primary" />
                    <span className="font-medium">{announcement.title}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <span className="text-default-500 text-sm line-clamp-1 max-w-[300px]">
                    {announcement.content || "-"}
                  </span>
                </TableCell>
                <TableCell>{formatTime(announcement.created_at)}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="flat"
                      isIconOnly
                      onPress={() => handlePreview(announcement)}
                      title="预览"
                    >
                      <Icon icon="lucide:eye" />
                    </Button>
                    <Button
                      size="sm"
                      variant="flat"
                      isIconOnly
                      onPress={() => handleEdit(announcement)}
                      title="编辑"
                    >
                      <Icon icon="lucide:edit" />
                    </Button>
                    <Button
                      size="sm"
                      variant="flat"
                      color="danger"
                      isIconOnly
                      onPress={() => handleDeleteClick(announcement)}
                      title="删除"
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
          onClose={() => {
            setModalOpen(false);
            setEditorTab("edit");
          }}
          size="3xl"
          scrollBehavior="inside"
        >
          <ModalContent>
            <ModalHeader>
              {editingAnnouncement ? "编辑公告" : "发布公告"}
            </ModalHeader>
            <ModalBody>
              <div className="flex flex-col gap-4">
                <Input
                  label="公告标题"
                  placeholder="请输入公告标题"
                  value={formData.title}
                  onValueChange={(value) => setFormData({ ...formData, title: value })}
                  isRequired
                />

                <Tabs
                  selectedKey={editorTab}
                  onSelectionChange={(key) => setEditorTab(key as string)}
                  aria-label="编辑器选项"
                >
                  <Tab
                    key="edit"
                    title={
                      <div className="flex items-center gap-2">
                        <Icon icon="lucide:edit-3" />
                        <span>编辑</span>
                      </div>
                    }
                  >
                    <div className="pt-2">
                      <Textarea
                        placeholder="请输入公告内容（支持 Markdown 格式）"
                        value={formData.content}
                        onValueChange={(value) => setFormData({ ...formData, content: value })}
                        minRows={12}
                        classNames={{
                          input: "font-mono text-sm",
                        }}
                      />
                      <p className="text-xs text-default-400 mt-2">
                        支持 Markdown 格式，可使用标题、列表、代码块、链接等
                      </p>
                    </div>
                  </Tab>
                  <Tab
                    key="preview"
                    title={
                      <div className="flex items-center gap-2">
                        <Icon icon="lucide:eye" />
                        <span>预览</span>
                      </div>
                    }
                  >
                    <div className="pt-2">
                      <Card className="min-h-[200px]">
                        <CardBody>
                          {formData.content ? (
                            <div className="markdown-body prose prose-sm dark:prose-invert max-w-none">
                              <ReactMarkdown>{formData.content}</ReactMarkdown>
                            </div>
                          ) : (
                            <p className="text-default-400 text-center py-8">
                              暂无内容，请在编辑标签页输入内容
                            </p>
                          )}
                        </CardBody>
                      </Card>
                    </div>
                  </Tab>
                </Tabs>

                {!editingAnnouncement && (
                  <div className="flex items-center gap-2 p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg">
                    <Icon icon="lucide:info" className="text-warning" />
                    <span className="text-sm text-warning-600 dark:text-warning-400">
                      发布后公告将立即推送给所有在线用户
                    </span>
                  </div>
                )}
              </div>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => {
                setModalOpen(false);
                setEditorTab("edit");
              }}>
                取消
              </Button>
              <Button color="primary" onPress={handleSave} isLoading={saving}>
                {editingAnnouncement ? "保存" : "发布"}
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
                确定要删除公告 <strong>「{deletingAnnouncement?.title}」</strong> 吗？此操作不可恢复。
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

        {/* 预览弹窗 */}
        <Modal
          isOpen={previewModalOpen}
          onClose={() => setPreviewModalOpen(false)}
          size="3xl"
          scrollBehavior="inside"
        >
          <ModalContent>
            <ModalHeader>
              <div className="flex items-center gap-2">
                <Icon icon="lucide:bell" className="text-primary" />
                {previewingAnnouncement?.title}
              </div>
            </ModalHeader>
            <ModalBody>
              {previewingAnnouncement && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-sm text-default-500">
                    <Icon icon="lucide:clock" />
                    <span>发布时间: {formatTime(previewingAnnouncement.created_at)}</span>
                  </div>
                  <Card>
                    <CardBody>
                      <div className="markdown-body prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown>{previewingAnnouncement.content}</ReactMarkdown>
                      </div>
                    </CardBody>
                  </Card>
                </div>
              )}
            </ModalBody>
            <ModalFooter>
              <Button
                variant="flat"
                onPress={() => {
                  setPreviewModalOpen(false);
                  if (previewingAnnouncement) {
                    handleEdit(previewingAnnouncement);
                  }
                }}
                startContent={<Icon icon="lucide:edit" />}
              >
                编辑
              </Button>
              <Button color="primary" onPress={() => setPreviewModalOpen(false)}>
                关闭
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </div>
    </DefaultLayout>
  );
}
