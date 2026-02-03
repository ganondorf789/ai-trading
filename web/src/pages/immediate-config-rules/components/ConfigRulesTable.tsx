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
  // 格式化条件详情（用于 Tooltip）
  const getConditionsDetail = (rule: ImmediateCopyConfigRule) => {
    const config = rule.config_data;
    const parts = [];
    
    if (config.min_trader_overall_score) {
      parts.push(`评分 ≥ ${config.min_trader_overall_score}`);
    }
    if (config.min_trader_leverage || config.max_trader_leverage) {
      const min = config.min_trader_leverage || 0;
      const max = config.max_trader_leverage || '∞';
      parts.push(`杠杆: ${min}x - ${max}x`);
    }
    if (config.min_position_value_usd || config.max_position_value_usd) {
      const min = config.min_position_value_usd || 0;
      const max = config.max_position_value_usd || '∞';
      parts.push(`仓位: $${min} - $${max}`);
    }
    if (config.min_coin_price || config.max_coin_price) {
      const min = config.min_coin_price || 0;
      const max = config.max_coin_price || '∞';
      parts.push(`价格: $${min} - $${max}`);
    }
    
    return parts;
  };

  // 格式化条件摘要
  const formatConditionsSummary = (rule: ImmediateCopyConfigRule) => {
    const config = rule.config_data;
    const count = [
      config.min_trader_overall_score,
      config.min_trader_leverage || config.max_trader_leverage,
      config.min_position_value_usd || config.max_position_value_usd,
      config.min_coin_price || config.max_coin_price,
    ].filter(Boolean).length;
    
    return count > 0 ? `${count} 项条件` : '-';
  };

  // 格式化跟单参数
  const formatParams = (rule: ImmediateCopyConfigRule) => {
    const config = rule.config_data;
    const ratio = config.copy_ratio ? `${(config.copy_ratio * 100).toFixed(0)}%` : '-';
    const maxSize = config.max_position_size_usd ? `$${config.max_position_size_usd}` : '-';
    const leverage = config.max_leverage ? `${config.max_leverage}x` : '-';
    
    return { ratio, maxSize, leverage };
  };

  return (
    <Table aria-label="Immediate config rules table">
      <TableHeader>
        <TableColumn>状态</TableColumn>
        <TableColumn>名称</TableColumn>
        <TableColumn>币种</TableColumn>
        <TableColumn>跟单条件</TableColumn>
        <TableColumn>跟单比例</TableColumn>
        <TableColumn>最大仓位</TableColumn>
        <TableColumn>最大杠杆</TableColumn>
        <TableColumn>操作</TableColumn>
      </TableHeader>
      <TableBody 
        emptyContent="暂无配置规则，点击上方按钮创建" 
        isLoading={loading} 
        loadingContent={<Spinner />}
      >
        {rules.map((rule) => {
          const params = formatParams(rule);
          const conditionsDetail = getConditionsDetail(rule);
          
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
                <Chip size="sm" color="primary" variant="flat">
                  {rule.symbol || '-'}
                </Chip>
              </TableCell>
              <TableCell>
                {conditionsDetail.length > 0 ? (
                  <Tooltip
                    content={
                      <div className="text-xs space-y-1 p-1">
                        {conditionsDetail.map((item, idx) => (
                          <div key={idx}>{item}</div>
                        ))}
                      </div>
                    }
                  >
                    <span className="text-sm cursor-help text-primary">
                      {formatConditionsSummary(rule)}
                    </span>
                  </Tooltip>
                ) : (
                  <span className="text-default-400">-</span>
                )}
              </TableCell>
              <TableCell>{params.ratio}</TableCell>
              <TableCell>{params.maxSize}</TableCell>
              <TableCell>{params.leverage}</TableCell>
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
