import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { ModelInfo, ModelName } from '../api/types';

interface Props {
  models: ModelInfo[];
  value: ModelName | '';
  defaultModel: ModelName | null;
  disabled: boolean;
  onChange: (model: ModelName) => void;
}

export default function ModelSelect({ models, value, defaultModel, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const selectedIndex = models.findIndex((model) => model.id === value);
  const [activeIndex, setActiveIndex] = useState(Math.max(selectedIndex, 0));
  const rootRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    if (open) optionRefs.current[activeIndex]?.focus();
  }, [activeIndex, open]);

  function chooseModel(model: ModelName) {
    onChange(model);
    setOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (models.length === 0 || disabled) return;

    if (event.key === 'Escape') {
      setOpen(false);
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      setActiveIndex((current) => {
        if (!open) return Math.max(selectedIndex, 0);
        return (current + direction + models.length) % models.length;
      });
      setOpen(true);
      return;
    }

    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      setActiveIndex(event.key === 'Home' ? 0 : models.length - 1);
      setOpen(true);
      return;
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (!open) {
        setActiveIndex(Math.max(selectedIndex, 0));
        setOpen(true);
      } else {
        const model = models[activeIndex];
        if (model) chooseModel(model.id);
      }
    }
  }

  return (
    <div
      ref={rootRef}
      className={`model-select${open ? ' model-select-open' : ''}`}
      onKeyDown={handleKeyDown}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        id="model"
        type="button"
        className="model-select-trigger"
        role="combobox"
        aria-label="Modelo"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="model-options"
        aria-activedescendant={open ? `model-option-${activeIndex}` : undefined}
        disabled={disabled || models.length === 0}
        onClick={() => {
          setActiveIndex(Math.max(selectedIndex, 0));
          setOpen((current) => !current);
        }}
      >
        <span className="model-select-value">
          <span className="model-select-name">
            {models.find((model) => model.id === value)?.id ?? 'Cargando modelos…'}
          </span>
          <span className="model-select-caption">
            {models.find((model) => model.id === value)?.version ?? 'Conectando con el servicio'}
          </span>
        </span>
        <span className="model-select-chevron" aria-hidden="true" />
      </button>

      {open && (
        <div id="model-options" className="model-options" role="listbox" aria-label="Modelos disponibles">
          {models.map((model, index) => {
            const isSelected = model.id === value;
            const isDefault = model.id === defaultModel;

            return (
              <button
                key={model.id}
                ref={(element) => {
                  optionRefs.current[index] = element;
                }}
                id={`model-option-${index}`}
                type="button"
                className={`model-option${isSelected ? ' model-option-selected' : ''}`}
                role="option"
                aria-selected={isSelected}
                tabIndex={activeIndex === index ? 0 : -1}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => chooseModel(model.id)}
              >
                <span className="model-option-copy">
                  <span className="model-option-name">{model.id}</span>
                  <span className="model-option-version">Versión {model.version}</span>
                </span>
                <span className="model-option-meta">
                  {isDefault && <span className="model-default-badge">Predeterminado</span>}
                  {isSelected && <span className="model-selected-mark" aria-hidden="true">✓</span>}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
