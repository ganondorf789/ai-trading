import { Select, SelectItem } from '@heroui/select';
import { Chip } from '@heroui/chip';
import type { BestSPreset } from '@/services/api';

interface PresetSelectorProps {
  presets: BestSPreset[];
  selectedPreset: string;
  onPresetChange: (preset: string) => void;
  isLoading?: boolean;
}

const presetColors: Record<string, 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'danger'> = {
  default: 'primary',
  safe: 'success',
  aggressive: 'danger',
  scalper: 'warning',
  swing: 'secondary',
  hot: 'danger',
};

export function PresetSelector({
  presets,
  selectedPreset,
  onPresetChange,
  isLoading,
}: PresetSelectorProps) {
  return (
    <Select
      label="筛选预设"
      placeholder="选择预设配置"
      selectedKeys={selectedPreset ? [selectedPreset] : []}
      onSelectionChange={(keys) => {
        const selected = Array.from(keys)[0] as string;
        if (selected) onPresetChange(selected);
      }}
      isLoading={isLoading}
      className="max-w-xs"
      size="sm"
      renderValue={(items) => {
        return items.map((item) => {
          const preset = presets.find((p) => p.key === item.key);
          return (
            <div key={item.key} className="flex items-center gap-2">
              <Chip size="sm" color={presetColors[item.key as string] || 'default'}>
                {preset?.name || item.key}
              </Chip>
            </div>
          );
        });
      }}
    >
      {presets.map((preset) => (
        <SelectItem key={preset.key} textValue={preset.name}>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <Chip size="sm" color={presetColors[preset.key] || 'default'}>
                {preset.name}
              </Chip>
            </div>
            <span className="text-xs text-default-400 mt-1">{preset.description}</span>
          </div>
        </SelectItem>
      ))}
    </Select>
  );
}
