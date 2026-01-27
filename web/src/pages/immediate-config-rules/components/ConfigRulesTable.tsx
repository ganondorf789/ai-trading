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
import { ImmediateCopyConfigRule } from "@/services/api";

interface ConfigRulesTableProps {
  rules: ImmediateCopyConfigRule[];
  loading: boolean;
  onEdit: (rule: ImmediateCopyConfigRule) => void;
  onDelete: (rule: ImmediateCopyConfigRule) => void;
  onToggleEnabled: (rule: ImmediateCopyConfigRule, enabled: boolean) => void;
}

export default function ConfigRulesTable({
  rules,
  loading,
  onEdit,
  onDelete,
  onToggleEnabled,
}: ConfigRulesTableProps) {
  const formatLeverageRange = (rule: ImmediateCopyConfigRule) => {
    if (rule.is_default) {
      return <Chip size="sm" color="secondary" variant="flat">兜底配置</Chip>;
    }
    return `${rule.leverage_min}x - ${rule.leverage_max}x`;
  };

  const formatConfigParams = (rule: ImmediateCopyConfigRule) => {
    const config = rule.config_data;
    const parts = [];
    
    if (config.max_position_size_usd) {
      parts.push(`最大$${config.max_position_size_usd}`);
    }
    if (config.copy_ratio) {
      parts.push(`比例${(config.copy_ratio * 100).toFixed(0)}%`);
    }
    if (config.min_trader_overall_score) {
      parts.push(`评分≥${config.min_trader_overall_score}`);
    }
    
    return parts.join(', ') || '-';
  };

  return (
    <Table aria-label="Immediate config rules table">
      <TableHeader>
        <TableColumn>名称</TableColumn>
        <TableColumn>杠杆区间</TableColumn>
        <TableColumn>优先级</TableColumn>
        <TableColumn>关键参数</TableColumn>
        <TableColumn>状态</TableColumn>
        <TableColumn>操作</TableColumn>
      </TableHeader>
      <TableBody 
        emptyContent="暂无配置规则，点击上方按钮创建" 
        isLoading={loading} 
        loadingContent={<Spinner />}
      >
        {rules.map((rule) => (
          <TableRow key={rule.id}>
            <TableCell>
              <Tooltip content={rule.description || '无描述'} isDisabled={!rule.description}>
                <span className="font-medium cursor-help">{rule.name}</span>
              </Tooltip>
            </TableCell>
            <TableCell>
              <span className="font-mono text-sm">
                {formatLeverageRange(rule)}
              </span>
            </TableCell>
            <TableCell>
              <Chip size="sm" variant="flat">{rule.priority}</Chip>
            </TableCell>
            <TableCell>
              <span className="text-sm text-default-600">
                {formatConfigParams(rule)}
              </span>
            </TableCell>
            <TableCell>
              <Switch
                size="sm"
                isSelected={rule.is_enabled}
                onValueChange={(enabled) => onToggleEnabled(rule, enabled)}
              />
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="light"
                  isIconOnly
                  onPress={() => onEdit(rule)}
                >
                  <Icon icon="lucide:edit" width={16} />
                </Button>
                <Button
                  size="sm"
                  variant="light"
                  color="danger"
                  isIconOnly
                  onPress={() => onDelete(rule)}
                >
                  <Icon icon="lucide:trash-2" width={16} />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
