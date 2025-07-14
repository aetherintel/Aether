import { useState } from 'react';
import { CheckIcon, Combobox, Group, Pill, PillsInput, useCombobox } from '@mantine/core';

interface TgChannelMultiSelectProps {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
}

const defaultChannel = ['freiesachsen', 'freiesHusum25813', 'jungenationalisten'];

export function TgChannelMultiSelect({
  value,
  onChange,
  placeholder = 'Search channels',
}: TgChannelMultiSelectProps) {
  const combobox = useCombobox({
    onDropdownClose: () => combobox.resetSelectedOption(),
    onDropdownOpen: () => combobox.updateSelectedOptionIndex('active'),
  });

  const [search, setSearch] = useState('');
  const [data, setData] = useState(defaultChannel);

  const exactMatch = data.some((item) => item === search);

  const handleSelect = (val: string) => {
    setSearch('');
    if (val === '$create') {
      setData((current) => [...current, search]);
      onChange([...value, search]);
    } else {
      onChange(value.includes(val) ? value.filter((v) => v !== val) : [...value, val]);
    }
  };

  const handleRemove = (val: string) => onChange(value.filter((v) => v !== val));

  const values = value.map((item) => (
    <Pill key={item} withRemoveButton onRemove={() => handleRemove(item)}>
      {item}
    </Pill>
  ));

  const options = data
    .filter((item) => item.toLowerCase().includes(search.trim().toLowerCase()))
    .map((item) => (
      <Combobox.Option value={item} key={item} active={value.includes(item)}>
        <Group gap="sm">
          {value.includes(item) ? <CheckIcon size={12} /> : null}
          <span>{item}</span>
        </Group>
      </Combobox.Option>
    ));

  return (
    <Combobox store={combobox} onOptionSubmit={handleSelect} withinPortal={false}>
      <Combobox.DropdownTarget>
        <PillsInput onClick={() => combobox.openDropdown()}>
          <Pill.Group>
            {values}

            <Combobox.EventsTarget>
              <PillsInput.Field
                onFocus={() => combobox.openDropdown()}
                onBlur={() => combobox.closeDropdown()}
                value={search}
                placeholder={placeholder}
                onChange={(e) => {
                  setSearch(e.currentTarget.value);
                  combobox.updateSelectedOptionIndex();
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Backspace' && search.length === 0) {
                    e.preventDefault();
                    handleRemove(value[value.length - 1]);
                  }
                }}
              />
            </Combobox.EventsTarget>
          </Pill.Group>
        </PillsInput>
      </Combobox.DropdownTarget>

      <Combobox.Dropdown>
        <Combobox.Options>
          {options}

          {!exactMatch && search.trim() && (
            <Combobox.Option value="$create">+ Create {search}</Combobox.Option>
          )}

          {exactMatch && search.trim() && options.length === 0 && (
            <Combobox.Empty>Nothing found</Combobox.Empty>
          )}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}
