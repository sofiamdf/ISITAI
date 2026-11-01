import { useRef, useState } from 'react';
import type { DragEvent } from 'react';
import { ALLOWED_TYPES } from '../api/config';

interface Props {
  file: File | null;
  previewUrl: string | null;
  disabled: boolean;
  onFile: (file: File) => void;
}

export default function ImagePicker({ file, previewUrl, disabled, onFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault(); // sin esto el navegador abre la imagen en la pestaña
    setDragging(false);
    if (disabled) return;
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFile(dropped);
  }

  return (
    <div
      className={`dropzone${dragging ? ' dropzone-active' : ''}`}
      onDragOver={(e) => {
        e.preventDefault(); // necesario para que el navegador permita soltar acá
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      {previewUrl && file ? (
        <>
          <img className="preview" src={previewUrl} alt={`Vista previa de ${file.name}`} />
          <p className="file-name">
            {file.name} · {(file.size / 1024).toFixed(0)} KiB
          </p>
        </>
      ) : (
        <p className="dropzone-text">Arrastrá una imagen acá</p>
      )}

      <button
        type="button"
        className="btn btn-secondary"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        {file ? 'Elegir otra imagen' : 'Elegir imagen'}
      </button>
      <p className="hint">JPEG, PNG o WebP · hasta 4 MiB</p>

      <input
        ref={inputRef}
        type="file"
        hidden
        accept={ALLOWED_TYPES.join(',')}
        onChange={(e) => {
          const chosen = e.target.files?.[0];
          if (chosen) onFile(chosen);
          e.target.value = ''; // permite volver a elegir el mismo archivo
        }}
      />
    </div>
  );
}