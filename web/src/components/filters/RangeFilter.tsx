import { Input } from '@heroui/input';

interface RangeFilterProps {
  label: string;
  minValue?: number;
  maxValue?: number;
  onMinChange: (value: number | undefined) => void;
  onMaxChange: (value: number | undefined) => void;
  endContent?: React.ReactNode;
  isInteger?: boolean;
  minPlaceholder?: string;
  maxPlaceholder?: string;
}

export function RangeFilter({
  label,
  minValue,
  maxValue,
  onMinChange,
  onMaxChange,
  endContent,
  isInteger = false,
  minPlaceholder = '最小',
  maxPlaceholder = '最大',
}: RangeFilterProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-default-600">{label}</span>
      <div className="flex items-center gap-1">
        <Input
          type="number"
          step={isInteger ? '1' : 'any'}
          size="sm"
          placeholder={minPlaceholder}
          value={minValue?.toString() || ''}
          onValueChange={(v) => onMinChange(v ? (isInteger ? parseInt(v) : parseFloat(v)) : undefined)}
          endContent={endContent}
        />
        <span className="text-default-400">-</span>
        <Input
          type="number"
          step={isInteger ? '1' : 'any'}
          size="sm"
          placeholder={maxPlaceholder}
          value={maxValue?.toString() || ''}
          onValueChange={(v) => onMaxChange(v ? (isInteger ? parseInt(v) : parseFloat(v)) : undefined)}
          endContent={endContent}
        />
      </div>
    </div>
  );
}
