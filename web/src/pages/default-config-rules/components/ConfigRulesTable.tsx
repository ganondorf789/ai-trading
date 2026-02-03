import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Chip,
  Spinner,
  Switch,
  Button,
  Tooltip,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { DefaultCopyConfigRule } from "@/services/api";

interface ConfigRulesTableProps {
  rules: DefaultCopyConfigRule[];
  loading: boolean;
  onEdit: (rule: DefaultCopyConfigRule) => void;
  onDelete: (rule: DefaultCopyConfigRule) => void;
  onToggleEnabled: (rule: DefaultCopyConfigRule, enabled: boolean) => void;
}

export default function ConfigRulesTable({
  rules,
  loading,
  onEdit,
  onDelete,
  onToggleEnabled,
}: ConfigRulesTableProps) {
  // 格式化杠杆区间
  const formatLeverageRange = (rule: DefaultCopyConfigRule) => {
    if (rule.is_default) {
      return <Chip size="sm" color="secondary" variant="flat">兜底</Chip>;
    }
    return `${rule.leverage_min}x - ${rule.leverage_max}x`;
  };

  // 格式化跟单参数
  const formatParams = (rule: DefaultCopyConfigRule) => {
    const config = rule.config_data;
    const ratio = config.copy_ratio ? `${(config.copy_ratio * 100).toFixed(0)}%` : '-';
    const maxSize = config.max_position_size_usd ? `$${config.max_position_size_usd}` : '-';
    
    return { ratio, maxSize };
  };

  return (
    <Table aria-label="Default config rules table">
      <TableHeader>
        <TableColumn>状态</TableColumn>
        <TableColumn>名称</TableColumn>
        <TableColumn>杠杆区间</TableColumn>
        <TableColumn>优先级</TableColumn>
        <TableColumn>跟单比例</TableColumn>
        <TableColumn>最大仓位</TableColumn>
        <TableColumn>操作</TableColumn>
      </TableHeader>
      <TableBody 
        emptyContent="暂无配置规则，点击上方按钮创建" 
        isLoading={loading} 
        loadingContent={<Spinner />}
      >
        {rules.map((rule) => {
          const params = formatParams(rule);
          
          return (
            <TableRow key={rule.id}>
              <TableCell>
                <Switch
                  size="sm"
                  isSelected={rule.is_enabled}
                  onValueChange={(enabled) => onToggleEnabled(rule, enabled)}
                />
              </TableCell>
              <TableCell>
                <div className="flex flex-col gap-0.5">
                  <span className="font-medium">{rule.name}</span>
                  {rule.description && (
                    <span className="text-xs text-default-400">{rule.description}</span>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <span className="text-sm whitespace-nowrap">
                  {formatLeverageRange(rule)}
                </span>
              </TableCell>
              <TableCell>
                <Chip size="sm" variant="flat">{rule.priority}</Chip>
              </TableCell>
              <TableCell>{params.ratio}</TableCell>
              <TableCell>{params.maxSize}</TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Tooltip content="编辑">
                    <Button
                      size="sm"
                      variant="light"
                      isIconOnly
                      onPress={() => onEdit(rule)}
                    >
                      <Icon icon="lucide:edit" width={16} />
                    </Button>
                  </Tooltip>
                  <Tooltip content="删除">
                    <Button
                      size="sm"
                      variant="light"
                      color="danger"
                      isIconOnly
                      onPress={() => onDelete(rule)}
                    >
                      <Icon icon="lucide:trash-2" width={16} />
                    </Button>
                  </Tooltip>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
