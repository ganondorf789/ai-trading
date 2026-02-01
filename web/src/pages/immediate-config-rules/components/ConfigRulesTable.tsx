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
  const formatConditions = (rule: ImmediateCopyConfigRule) => {
    const config = rule.config_data;
    const parts = [];
    
    if (config.min_trader_overall_score) {
      parts.push(`评分≥${config.min_trader_overall_score}`);
    }
    if (config.min_trader_leverage) {
      parts.push(`杠杆≥${config.min_trader_leverage}x`);
    }
    if (config.max_trader_leverage) {
      parts.push(`杠杆≤${config.max_trader_leverage}x`);
    }
    if (config.min_position_value_usd) {
      parts.push(`仓位≥$${config.min_position_value_usd}`);
    }
    if (config.max_position_value_usd) {
      parts.push(`仓位≤$${config.max_position_value_usd}`);
    }
    if (config.min_coin_price) {
      parts.push(`价格≥$${config.min_coin_price}`);
    }
    if (config.max_coin_price) {
      parts.push(`价格≤$${config.max_coin_price}`);
    }
    
    return parts.length > 0 ? parts.join(', ') : '无条件限制';
  };

  const formatParams = (rule: ImmediateCopyConfigRule) => {
    const config = rule.config_data;
    const parts = [];
    
    if (config.copy_ratio) {
      parts.push(`比例${(config.copy_ratio * 100).toFixed(0)}%`);
    }
    if (config.max_position_size_usd) {
      parts.push(`最大$${config.max_position_size_usd}`);
    }
    if (config.max_leverage) {
      parts.push(`${config.max_leverage}x`);
    }
    
    return parts.join(', ') || '-';
  };

  return (
    <Table aria-label="Immediate config rules table">
      <TableHeader>
        <TableColumn>名称</TableColumn>
        <TableColumn>币种</TableColumn>
        <TableColumn>跟单条件</TableColumn>
        <TableColumn>跟单参数</TableColumn>
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
              <Chip size="sm" color="primary" variant="flat">
                {rule.symbol || '-'}
              </Chip>
            </TableCell>
            <TableCell>
              <span className="text-sm text-default-600">
                {formatConditions(rule)}
              </span>
            </TableCell>
            <TableCell>
              <span className="text-sm text-default-600">
                {formatParams(rule)}
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
