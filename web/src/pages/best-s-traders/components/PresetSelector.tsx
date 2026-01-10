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

const presetIcons: Record<string, string> = {
  default: '📊',
  safe: '🛡️',
  aggressive: '🔥',
  scalper: '⚡',
  swing: '🌊',
  hot: '🚀',
};

export function PresetSelector({
  presets,
  selectedPreset,
  onPresetChange,
}: PresetSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {presets.map((preset) => {
        const isSelected = selectedPreset === preset.key;
        const color = presetColors[preset.key] || 'default';
        const icon = presetIcons[preset.key] || '📌';

        return (
          <Chip
            key={preset.key}
            color={color}
            variant={isSelected ? 'solid' : 'flat'}
            className={`cursor-pointer transition-all hover:scale-105 ${
              isSelected ? 'shadow-md' : 'opacity-70 hover:opacity-100'
            }`}
            onClick={() => onPresetChange(preset.key)}
            startContent={<span>{icon}</span>}
          >
            {preset.name}
          </Chip>
        );
      })}
    </div>
  );
}
