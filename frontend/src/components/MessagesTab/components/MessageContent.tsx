import React, { useState, useRef, useLayoutEffect } from 'react';
import { Button, Anchor } from '@mantine/core';
import { escapeRegExp } from '../utils';
import classes from '../MessagesTab.module.css';

interface MessageContentProps {
  message: {
    original_text: string;
    translated_text?: string | null;
    original_language?: string;
    translation_status?: string;
  };
  searchQuery?: string;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

const useMeasureText = () => {
    const measureRef = useRef<HTMLDivElement>(null);
    const [needsTruncation, setNeedsTruncation] = useState(false);

    useLayoutEffect(() => {
        if (measureRef.current) {
            const element = measureRef.current;
            const computedStyle = window.getComputedStyle(element);
            const lineHeight = parseFloat(computedStyle.lineHeight);
            const actualHeight = element.scrollHeight;
            const lineCount = Math.round(actualHeight / lineHeight);
            setNeedsTruncation(lineCount > 3);
        }
    });

    return { measureRef, needsTruncation };
};

function highlightText(text: string, query: string) {
    const urlRegex = /https?:\/\/[^\s]+/gi;
    const queryRegex = query ? new RegExp(`(${escapeRegExp(query)})`, 'gi') : null;
    const urlParts = text.split(urlRegex);
    const urls = text.match(urlRegex);
    const result: React.ReactNode[] = [];

    urlParts.forEach((part, i) => {
        if (queryRegex) {
            const highlighted = part
                .split(queryRegex)
                .map((p, idx) => queryRegex.test(p) ? <mark key={`highlight-${i}-${idx}`}>{p}</mark> : p);
            result.push(...highlighted);
        } else {
            result.push(part);
        }

        if (urls && urls[i]) {
            const url = urls[i];
            if (queryRegex) {
                const highlightedLink = url.split(queryRegex).map((p, idx) =>
                    queryRegex.test(p) ? <mark key={`link-highlight-${i}-${idx}`}>{p}</mark> : p);
                result.push(
                    <Anchor key={`link-${i}`} href={url} fz="xs" target="_blank" rel="noopener noreferrer" style={{ lineHeight: 1 }}>
                        {highlightedLink}
                    </Anchor>
                );
            } else {
                result.push(
                    <Anchor key={`link-${i}`} href={url} fz="sm" target="_blank" rel="noopener noreferrer" style={{ lineHeight: 1 }}>
                        {url}
                    </Anchor>
                );
            }
        }
    });
    return result;
}

export const MessageContent: React.FC<MessageContentProps> = ({
  message,
  searchQuery = '',
  isExpanded,
  onToggleExpand,
}) => {
  const { measureRef, needsTruncation } = useMeasureText();
  const [showOriginal, setShowOriginal] = useState(false);
  
  const hasTranslation =
    !!message.translated_text &&
    message.translated_text.trim().length > 0 &&
    message.translation_status === 'completed';

  const displayedText = (showOriginal || !hasTranslation ? message.original_text : message.translated_text) || '';
  const handleToggleLanguage = () => setShowOriginal((prev) => !prev);
  const languageLabel = message.original_language && message.original_language.length > 0
    ? message.original_language.toUpperCase() : 'N/A';

  return (
    <div className={classes.messageContent}>
      <div ref={measureRef} className={`${classes.messageText} ${isExpanded ? classes.messageTextExpanded : classes.messageTextTruncated}`}>
        {highlightText(displayedText, searchQuery || '')}
      </div>

      <div className={classes.actionsRow}>
        {needsTruncation && (
          <Button variant="subtle" size="xs" onClick={onToggleExpand} className={classes.expandButton}>
            {isExpanded ? 'Show less' : 'Show more'}
          </Button>
        )}

        {hasTranslation && (
          <Button variant="subtle" size="xs" onClick={handleToggleLanguage} className={classes.languageToggle}>
            {showOriginal ? 'View German translation' : `View original (${languageLabel})`}
          </Button>
        )}
      </div>
    </div>
  );
};
