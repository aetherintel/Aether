import { useMemo } from 'react';
import type { OutputChannelEntry } from '../types/caseFileDetail';
import { Checkbox, Stack } from '@mantine/core';

interface TgChannelsCheckboxListProps {
  structuredChannels: [string, OutputChannelEntry][];
  selectedTgChannelIds: string[];
  setSelectedTgChannelIds: React.Dispatch<React.SetStateAction<string[]>>;
}

const TgChannelsCheckboxList: React.FC<TgChannelsCheckboxListProps> = ({ structuredChannels, selectedTgChannelIds, setSelectedTgChannelIds }) => {
    const handleParentChange = (parentId: string, childIds: string[]) => {
        const allChildrenSelected = childIds.every(id => selectedTgChannelIds.includes(id));
        setSelectedTgChannelIds((current) =>
        allChildrenSelected
            ? current.filter(id => !childIds.includes(id) && id !== parentId)
            : [...new Set([...current, parentId, ...childIds])]
        );
    };

    const handleChildChange = (childId: string, parentId?: string) => {
        setSelectedTgChannelIds((current) => {
        const exists = current.includes(childId);
        const updated = exists
            ? current.filter(id => id !== childId)
            : [...current, childId];

        // Optional: Update parent if all children are unchecked
        if (parentId) {
            const allChildrenUnchecked = Object.values(structuredChannelsById[parentId]?.recommended || {})
            .every(c => !updated.includes(c.channel.channel_id));

            if (allChildrenUnchecked) {
            return updated.filter(id => id !== parentId);
            }
        }

        return updated;
        });
    };

    // Create a mapping for easy access
    const structuredChannelsById = useMemo(() => {
        const map: Record<string, typeof structuredChannels[0][1]> = {};
        structuredChannels.forEach(([, groupValue]) => {
        if (groupValue.channel) {
            map[groupValue.channel.channel_id] = groupValue;
        }
        });
        return map;
    }, [structuredChannels]);

    return (
        <Stack>
        {structuredChannels.map(([, groupValue]) => {
            if (!groupValue.channel) {return null;}

            const parentChannel = groupValue.channel;
            const parentId = parentChannel.channel_id;

            const recommendedChannels = Object.entries(groupValue.recommended);
            const recommendedIds = recommendedChannels.map(([_, rec]) => rec.channel.channel_id);

            const allChecked = recommendedIds.every(id => selectedTgChannelIds.includes(id));

            const parentIsChecked = selectedTgChannelIds.includes(parentId);
            const indeterminate = recommendedIds.some(id => selectedTgChannelIds.includes(id)) && !allChecked;

            return (
            <div key={parentId}>
                <Checkbox
                label={parentChannel.username}
                checked={parentIsChecked}
                indeterminate={indeterminate}
                onChange={() => handleParentChange(parentId, recommendedIds)}
                />
                <Stack pl="md" mt="xs">
                {recommendedChannels.map(([recUsername, recData]) => (
                    <Checkbox
                    key={recData.channel.channel_id}
                    label={recUsername}
                    checked={selectedTgChannelIds.includes(recData.channel.channel_id)}
                    onChange={() => handleChildChange(recData.channel.channel_id, parentId)}
                    />
                ))}
                </Stack>
            </div>
            );
        })}
        </Stack>
    );
}

export default TgChannelsCheckboxList;