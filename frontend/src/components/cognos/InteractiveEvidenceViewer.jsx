import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Crop,
  Highlighter,
  Square,
  ArrowUpRight,
  Type,
  Undo2,
  Redo2,
  Copy,
  Download,
  X,
  Check,
  Trash2,
  MousePointer,
  Layers,
  Sparkles,
  Scissors
} from 'lucide-react';

const PALETTE = [
  { id: 'yellow', name: 'Yellow', hex: '#eab308', bg: 'rgba(255, 230, 0, 0.35)', border: '#ca8a04' },
  { id: 'red', name: 'Red', hex: '#ef4444', bg: 'rgba(255, 80, 80, 0.30)', border: '#dc2626' },
  { id: 'green', name: 'Green', hex: '#22c55e', bg: 'rgba(80, 200, 120, 0.30)', border: '#16a34a' },
  { id: 'blue', name: 'Blue', hex: '#3b82f6', bg: 'rgba(80, 140, 255, 0.30)', border: '#2563eb' },
  { id: 'purple', name: 'Purple', hex: '#a855f7', bg: 'rgba(168, 85, 247, 0.30)', border: '#9333ea' },
];

export default function InteractiveEvidenceViewer({
  isOpen,
  onClose,
  imageUrl,
  blob,
  evidence,
  title,
  previewMeta
}) {
  if (!isOpen || !imageUrl) return null;

  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const textInputRef = useRef(null);

  // Natural Image Dimensions
  const [naturalSize, setNaturalSize] = useState({ width: 1200, height: 1600 });
  const [imageLoaded, setImageLoaded] = useState(false);

  // Viewport / Transform State
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState({ x: 0, y: 0 });

  // Tool Selection: 'select' | 'highlight' | 'rectangle' | 'arrow' | 'text' | 'crop'
  const [activeTool, setActiveTool] = useState('highlight');
  const [selectedColor, setSelectedColor] = useState(PALETTE[0]); // Yellow 0.35 default
  
  // Text In-Place Editing State
  const [editingText, setEditingText] = useState(null); // { id: string | null, srcX: number, srcY: number, text: string }

  // Annotations & Selection (All stored strictly in ORIGINAL SOURCE IMAGE coordinates)
  const [annotations, setAnnotations] = useState([]);
  const [selectedAnnoId, setSelectedAnnoId] = useState(null);

  // Crop State (Stored strictly in ORIGINAL SOURCE IMAGE coordinates)
  const [appliedCrop, setAppliedCrop] = useState(null); // { x, y, width, height } in src coords
  const [draftCrop, setDraftCrop] = useState(null); // { startX, startY, currentX, currentY, isReady }

  // Dragging / Resizing Active State
  const [activeDrag, setActiveDrag] = useState(null); 
  // { mode: 'draw' | 'move' | 'resize-nw' | 'resize-ne' | 'resize-se' | 'resize-sw', annoId, startSrcX, startSrcY, origAnno, currentSrcX, currentSrcY }

  // History for Undo/Redo
  const [history, setHistory] = useState([{ annotations: [], appliedCrop: null }]);
  const [historyIndex, setHistoryIndex] = useState(0);

  // UI status / Toast feedback
  const [toastMessage, setToastMessage] = useState(null);
  const [isAnnotatedView, setIsAnnotatedView] = useState(false);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2800);
  };

  // Storage Key derived strictly from run_id + evidence_id
  const getStorageKey = useCallback(() => {
    const runId = evidence?.run_id || 
      (typeof evidence?.source_document_url === 'string' ? evidence.source_document_url.match(/runs\/(\d+)/)?.[1] : null) || 
      'run_default';
    const evId = evidence?.evidence_id || evidence?.test_case_id || evidence?.section || 'evidence_default';
    return `cognos_evidence_annotations_${runId}_${evId}`;
  }, [evidence]);

  // ── CENTRALIZED COORDINATE TRANSFORMATION ENGINE ─────────────────────────
  // Active Crop Offsets in Source Image Space
  const cropX = appliedCrop ? appliedCrop.x : 0;
  const cropY = appliedCrop ? appliedCrop.y : 0;
  const cropW = appliedCrop ? appliedCrop.width : naturalSize.width;
  const cropH = appliedCrop ? appliedCrop.height : naturalSize.height;

  // 1. Source Point -> Display Viewport Point
  const sourceToDisplayPoint = useCallback((srcX, srcY) => {
    return {
      x: srcX - cropX,
      y: srcY - cropY
    };
  }, [cropX, cropY]);

  // 2. Source Rect -> Display Viewport Rect
  const sourceToDisplayRect = useCallback((srcRect) => {
    return {
      x: srcRect.x - cropX,
      y: srcRect.y - cropY,
      width: srcRect.width,
      height: srcRect.height
    };
  }, [cropX, cropY]);

  // 3. Pointer (Client Event) -> Source Image Point (Reverse Transform)
  const getSourceCoords = useCallback((e) => {
    if (!canvasRef.current) return { x: 0, y: 0 };
    const rect = canvasRef.current.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    // Compute relative offset in container space [0, cropW] and [0, cropH]
    const mouseRelX = (clientX - rect.left) / zoom;
    const mouseRelY = (clientY - rect.top) / zoom;

    const srcX = cropX + mouseRelX;
    const srcY = cropY + mouseRelY;

    return {
      x: Math.round(Math.min(Math.max(srcX, 0), naturalSize.width)),
      y: Math.round(Math.min(Math.max(srcY, 0), naturalSize.height))
    };
  }, [cropX, cropY, zoom, naturalSize]);

  // Diagnostic Coordinate Logging for Verification
  useEffect(() => {
    if (annotations.length > 0) {
      const firstAnno = annotations[0];
      const disp = sourceToDisplayRect(firstAnno);
      console.log("ORIGINAL ANNOTATION:", { x: firstAnno.x, y: firstAnno.y, width: firstAnno.width, height: firstAnno.height });
      console.log("CROP:", { x: cropX, y: cropY, width: cropW, height: cropH });
      console.log("DISPLAY SIZE:", { width: cropW, height: cropH });
      console.log("TRANSFORMED RECT:", disp);
    }
  }, [annotations, cropX, cropY, cropW, cropH, sourceToDisplayRect]);

  // Push new state to undo/redo history
  const pushHistory = useCallback((newAnnotations, newCrop) => {
    const nextHistory = history.slice(0, historyIndex + 1);
    nextHistory.push({
      annotations: newAnnotations,
      appliedCrop: newCrop !== undefined ? newCrop : appliedCrop
    });
    setHistory(nextHistory);
    setHistoryIndex(nextHistory.length - 1);
    setAnnotations(newAnnotations);
    if (newCrop !== undefined) setAppliedCrop(newCrop);
    setIsAnnotatedView(newAnnotations.length > 0 || (newCrop !== undefined ? newCrop !== null : appliedCrop !== null));
  }, [history, historyIndex, appliedCrop]);

  const handleUndo = useCallback(() => {
    if (historyIndex > 0) {
      const targetState = history[historyIndex - 1];
      setHistoryIndex(historyIndex - 1);
      setAnnotations(targetState.annotations);
      setAppliedCrop(targetState.appliedCrop);
      setSelectedAnnoId(null);
      setEditingText(null);
      setIsAnnotatedView(targetState.annotations.length > 0 || targetState.appliedCrop !== null);
    }
  }, [history, historyIndex]);

  const handleRedo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const targetState = history[historyIndex + 1];
      setHistoryIndex(historyIndex + 1);
      setAnnotations(targetState.annotations);
      setAppliedCrop(targetState.appliedCrop);
      setSelectedAnnoId(null);
      setEditingText(null);
      setIsAnnotatedView(targetState.annotations.length > 0 || targetState.appliedCrop !== null);
    }
  }, [history, historyIndex]);

  // Handle Image Load & Initial Fit on Opening
  useEffect(() => {
    if (!isOpen || !imageUrl) return;

    // Reset view transform, pan, and crop on opening Full Size
    setAppliedCrop(null);
    setDraftCrop(null);
    setSelectedAnnoId(null);
    setEditingText(null);
    setPan({ x: 0, y: 0 });
    setHistory([{ annotations: [], appliedCrop: null }]);
    setHistoryIndex(0);
    setIsAnnotatedView(false);

    let active = true;

    async function processBlobAndInit() {
      let editorBlob = blob;
      if (!editorBlob && imageUrl.startsWith('blob:')) {
        try {
          const r = await fetch(imageUrl);
          editorBlob = await r.blob();
        } catch (e) {}
      }

      let editorSha256 = "N/A";
      if (editorBlob) {
        try {
          const buffer = await editorBlob.arrayBuffer();
          const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
          editorSha256 = Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, "0")).join("");
        } catch (e) {
          editorSha256 = "hash_calc_error";
        }
      }

      const img = new window.Image();
      img.src = imageUrl;
      img.onload = () => {
        if (!active) return;
        const nw = img.naturalWidth || 1718;
        const nh = img.naturalHeight || 171;
        setNaturalSize({ width: nw, height: nh });
        setImageLoaded(true);

        const sameBlob = (blob && previewMeta?.size && blob.size === previewMeta.size) || (editorBlob && previewMeta?.size && editorBlob.size === previewMeta.size) ? "YES" : "NO";
        const sameHash = (previewMeta?.sha256 && editorSha256 !== "N/A" && previewMeta.sha256 === editorSha256) ? "YES" : "NO";

        console.log("=== SOURCE IMAGE IDENTITY ===\n");
        console.log("preview:");
        console.log(`    url: ${previewMeta?.url || imageUrl}`);
        console.log(`    size: ${previewMeta?.size || (editorBlob ? editorBlob.size : 'N/A')} bytes`);
        console.log(`    type: ${previewMeta?.type || (editorBlob ? editorBlob.type : 'image/png')}`);
        console.log(`    sha256: ${previewMeta?.sha256 || editorSha256}`);
        console.log(`    naturalWidth: ${previewMeta?.naturalWidth || nw}`);
        console.log(`    naturalHeight: ${previewMeta?.naturalHeight || nh}\n`);

        console.log("editor:");
        console.log(`    url: ${imageUrl}`);
        console.log(`    size: ${editorBlob ? editorBlob.size : 'N/A'} bytes`);
        console.log(`    type: ${editorBlob ? editorBlob.type : 'image/png'}`);
        console.log(`    sha256: ${editorSha256}`);
        console.log(`    naturalWidth: ${nw}`);
        console.log(`    naturalHeight: ${nh}\n`);

        console.log(`sameBlob:\n    ${sameBlob}\n`);
        console.log(`sameHash:\n    ${sameHash}\n`);

        setTimeout(() => {
          if (!active) return;
          if (containerRef.current) {
            const rect = containerRef.current.getBoundingClientRect();
            const scaleX = (rect.width - 60) / nw;
            const scaleY = (rect.height - 60) / nh;
            const fitZoom = Math.min(scaleX, scaleY);
            const clampedZoom = Math.min(Math.max(fitZoom, 0.05), 3.0);
            setZoom(clampedZoom);
            setPan({ x: 0, y: 0 });

            console.log("=== SOURCE SNAPSHOT EDITOR INIT ===");
            console.log("source URL:", imageUrl);
            console.log("blob size:", editorBlob ? `${editorBlob.size} bytes` : 'N/A');
            console.log("naturalWidth:", nw);
            console.log("naturalHeight:", nh);
            console.log("editor canvas:", { width: nw, height: nh });
            console.log("viewport:", { width: Math.round(rect.width), height: Math.round(rect.height) });
            console.log("zoom:", clampedZoom);
            console.log("panX:", 0);
            console.log("panY:", 0);
            console.log("crop:", null);
          }
        }, 50);
      };
    }

    processBlobAndInit();

    return () => {
      active = false;
    };
  }, [isOpen, imageUrl, blob, previewMeta]);

  // Debounced Auto-Save to localStorage on every annotation or crop change
  useEffect(() => {
    if (!imageLoaded) return;
    const timer = setTimeout(() => {
      const key = getStorageKey();
      if (annotations.length > 0 || appliedCrop !== null) {
        const payload = {
          version: 1,
          runId: evidence?.run_id,
          evidenceId: evidence?.evidence_id || evidence?.test_case_id,
          appliedCrop,
          annotations,
          zoom,
          pan,
          updatedAt: new Date().toISOString()
        };
        localStorage.setItem(key, JSON.stringify(payload));
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [annotations, appliedCrop, zoom, pan, imageLoaded, getStorageKey, evidence]);

  // Handle Image Load fallback from DOM img element
  const handleImageLoad = (e) => {
    const nw = e.target.naturalWidth || 1718;
    const nh = e.target.naturalHeight || 171;
    setNaturalSize({ width: nw, height: nh });
    setImageLoaded(true);
  };

  // Zoom helpers
  const handleZoomChange = (newZoom) => {
    const clamped = Math.min(Math.max(newZoom, 0.05), 4.0);
    setZoom(clamped);
  };

  const handleFitScreen = () => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const effectiveW = appliedCrop ? appliedCrop.width : naturalSize.width;
    const effectiveH = appliedCrop ? appliedCrop.height : naturalSize.height;
    const scaleX = (rect.width - 60) / effectiveW;
    const scaleY = (rect.height - 60) / effectiveH;
    const fitZoom = Math.min(scaleX, scaleY);
    setZoom(Math.min(Math.max(fitZoom, 0.05), 3.0));
    setPan({ x: 0, y: 0 });
  };

  const handleFitWidth = () => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const effectiveW = appliedCrop ? appliedCrop.width : naturalSize.width;
    const scale = (rect.width - 60) / effectiveW;
    setZoom(Math.min(Math.max(scale, 0.05), 4.0));
    setPan({ x: 0, y: 0 });
  };

  // Reset to Pristine Authoritative DSD Image
  const handleReset = () => {
    setAnnotations([]);
    setAppliedCrop(null);
    setDraftCrop(null);
    setActiveDrag(null);
    setSelectedAnnoId(null);
    setEditingText(null);
    setHistory([{ annotations: [], appliedCrop: null }]);
    setHistoryIndex(0);
    setIsAnnotatedView(false);

    // Remove from localStorage
    const key = getStorageKey();
    localStorage.removeItem(key);

    handleFitScreen();
    showToast("Evidence view reset to original authoritative snapshot.");
  };

  // Reset Crop Only (Return to Full DSD Page while preserving all annotations)
  const handleResetCropOnly = () => {
    pushHistory(annotations, null);
    handleFitScreen();
    showToast("Crop removed. Full DSD restored with annotations.");
  };

  // Pointer Interaction Handlers
  const handlePointerDown = (e) => {
    // If clicking on a button, input, or textarea, ignore canvas drawing
    if (e.target.closest('button') || e.target.closest('input') || e.target.closest('textarea')) {
      return;
    }

    // If text edit is active and clicked outside, commit it
    if (editingText) {
      handleCommitText();
    }

    if (activeTool === 'select' || e.button === 1 || e.altKey) {
      setIsPanning(true);
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      setStartPan({ x: clientX - pan.x, y: clientY - pan.y });
      return;
    }

    const { x, y } = getSourceCoords(e);

    if (activeTool === 'crop') {
      setDraftCrop({ startX: x, startY: y, currentX: x, currentY: y, isReady: false });
    } else if (activeTool === 'text') {
      setEditingText({ id: null, srcX: x, srcY: y, text: '' });
      setSelectedAnnoId(null);
    } else if (['highlight', 'rectangle', 'arrow'].includes(activeTool)) {
      setActiveDrag({
        mode: 'draw',
        type: activeTool,
        startX: x,
        startY: y,
        currentX: x,
        currentY: y,
        color: selectedColor
      });
      setSelectedAnnoId(null);
    }
  };

  const handlePointerMove = (e) => {
    if (isPanning) {
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      setPan({
        x: clientX - startPan.x,
        y: clientY - startPan.y
      });
      return;
    }

    if (draftCrop && !draftCrop.isReady) {
      const { x, y } = getSourceCoords(e);
      setDraftCrop(prev => ({ ...prev, currentX: x, currentY: y }));
      return;
    }

    if (!activeDrag) return;

    const { x, y } = getSourceCoords(e);

    if (activeDrag.mode === 'draw') {
      setActiveDrag(prev => ({ ...prev, currentX: x, currentY: y }));
    } else if (activeDrag.mode === 'move') {
      const dx = x - activeDrag.startSrcX;
      const dy = y - activeDrag.startSrcY;
      const orig = activeDrag.origAnno;

      const nextAnnotations = annotations.map(anno => {
        if (anno.id === activeDrag.annoId) {
          if (anno.type === 'arrow') {
            return {
              ...anno,
              x1: orig.x1 + dx,
              y1: orig.y1 + dy,
              x2: orig.x2 + dx,
              y2: orig.y2 + dy,
            };
          }
          return {
            ...anno,
            x: Math.max(0, Math.min(orig.x + dx, naturalSize.width - (orig.width || 80))),
            y: Math.max(0, Math.min(orig.y + dy, naturalSize.height - (orig.height || 26))),
          };
        }
        return anno;
      });
      setAnnotations(nextAnnotations);
    } else if (activeDrag.mode.startsWith('resize-')) {
      const handle = activeDrag.mode.replace('resize-', '');
      const orig = activeDrag.origAnno;
      const dx = x - activeDrag.startSrcX;
      const dy = y - activeDrag.startSrcY;

      let newX = orig.x;
      let newY = orig.y;
      let newW = orig.width;
      let newH = orig.height;

      if (handle === 'nw') {
        newX = Math.min(orig.x + dx, orig.x + orig.width - 10);
        newY = Math.min(orig.y + dy, orig.y + orig.height - 10);
        newW = orig.width - (newX - orig.x);
        newH = orig.height - (newY - orig.y);
      } else if (handle === 'ne') {
        newY = Math.min(orig.y + dy, orig.y + orig.height - 10);
        newW = Math.max(10, orig.width + dx);
        newH = orig.height - (newY - orig.y);
      } else if (handle === 'se') {
        newW = Math.max(10, orig.width + dx);
        newH = Math.max(10, orig.height + dy);
      } else if (handle === 'sw') {
        newX = Math.min(orig.x + dx, orig.x + orig.width - 10);
        newW = orig.width - (newX - orig.x);
        newH = Math.max(10, orig.height + dy);
      }

      const nextAnnotations = annotations.map(anno => {
        if (anno.id === activeDrag.annoId) {
          return { ...anno, x: newX, y: newY, width: newW, height: newH };
        }
        return anno;
      });
      setAnnotations(nextAnnotations);
    }
  };

  const handlePointerUp = () => {
    if (isPanning) {
      setIsPanning(false);
      return;
    }

    if (draftCrop && !draftCrop.isReady) {
      const x = Math.min(draftCrop.startX, draftCrop.currentX);
      const y = Math.min(draftCrop.startY, draftCrop.currentY);
      const width = Math.abs(draftCrop.currentX - draftCrop.startX);
      const height = Math.abs(draftCrop.currentY - draftCrop.startY);

      if (width > 15 && height > 15) {
        setDraftCrop({ x, y, width, height, isReady: true });
      } else {
        setDraftCrop(null);
      }
      return;
    }

    if (!activeDrag) return;

    if (activeDrag.mode === 'draw') {
      const x = Math.min(activeDrag.startX, activeDrag.currentX);
      const y = Math.min(activeDrag.startY, activeDrag.currentY);
      const width = Math.abs(activeDrag.currentX - activeDrag.startX);
      const height = Math.abs(activeDrag.currentY - activeDrag.startY);

      if (activeDrag.type === 'arrow') {
        const dx = activeDrag.currentX - activeDrag.startX;
        const dy = activeDrag.currentY - activeDrag.startY;
        if (Math.hypot(dx, dy) > 15) {
          const newAnno = {
            id: `anno_${Date.now()}`,
            type: 'arrow',
            x1: activeDrag.startX,
            y1: activeDrag.startY,
            x2: activeDrag.currentX,
            y2: activeDrag.currentY,
            color: activeDrag.color
          };
          pushHistory([...annotations, newAnno]);
          setSelectedAnnoId(newAnno.id);
        }
      } else if (width >= 6 && height >= 6) {
        // True Snipping-Tool rectangle or highlight
        const newAnno = {
          id: `anno_${Date.now()}`,
          type: activeDrag.type, // 'highlight' | 'rectangle'
          x,
          y,
          width,
          height,
          color: activeDrag.color
        };
        pushHistory([...annotations, newAnno]);
        setSelectedAnnoId(newAnno.id);
      }
    } else if (['move', 'resize-nw', 'resize-ne', 'resize-se', 'resize-sw'].includes(activeDrag.mode)) {
      pushHistory(annotations);
    }

    setActiveDrag(null);
  };

  // Wheel handling: Wheel -> Pan; Ctrl+Wheel -> Zoom
  const handleWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
      handleZoomChange(zoom * zoomFactor);
    } else {
      setPan(prev => ({
        x: prev.x - e.deltaX * 0.75,
        y: prev.y - e.deltaY * 0.75
      }));
    }
  };

  // Delete Selected Annotation
  const handleDeleteSelected = useCallback(() => {
    if (selectedAnnoId) {
      const nextAnnos = annotations.filter(a => a.id !== selectedAnnoId);
      pushHistory(nextAnnos);
      setSelectedAnnoId(null);
      showToast("Annotation deleted.");
    }
  }, [selectedAnnoId, annotations, pushHistory]);

  // Apply or Cancel Crop Handlers
  const handleApplyCrop = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    console.log("APPLY CROP CLICKED");

    if (!draftCrop) {
      console.log("No draft crop found");
      showToast("Select a valid crop region.");
      return;
    }

    const cropBoxX = draftCrop.x !== undefined ? draftCrop.x : Math.min(draftCrop.startX, draftCrop.currentX);
    const cropBoxY = draftCrop.y !== undefined ? draftCrop.y : Math.min(draftCrop.startY, draftCrop.currentY);
    const cropBoxW = draftCrop.width !== undefined ? draftCrop.width : Math.abs(draftCrop.currentX - draftCrop.startX);
    const cropBoxH = draftCrop.height !== undefined ? draftCrop.height : Math.abs(draftCrop.currentY - draftCrop.startY);

    console.log("CURRENT CROP:", { x: cropBoxX, y: cropBoxY, width: cropBoxW, height: cropBoxH });
    console.log("SOURCE IMAGE SIZE:", naturalSize);

    if (cropBoxW <= 10 || cropBoxH <= 10) {
      showToast("Select a valid crop region.");
      return;
    }

    // Normalize within original source image bounds
    const normalizedCrop = {
      x: Math.max(0, Math.min(cropBoxX, naturalSize.width - 10)),
      y: Math.max(0, Math.min(cropBoxY, naturalSize.height - 10)),
      width: Math.min(cropBoxW, naturalSize.width - cropBoxX),
      height: Math.min(cropBoxH, naturalSize.height - cropBoxY)
    };

    console.log("NORMALIZED CROP:", normalizedCrop);

    setDraftCrop(null);
    setActiveTool('select');
    pushHistory(annotations, normalizedCrop);

    // Auto fit cropped area to container smoothly
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const scaleX = (rect.width - 80) / normalizedCrop.width;
      const scaleY = (rect.height - 80) / normalizedCrop.height;
      setZoom(Math.min(Math.max(Math.min(scaleX, scaleY), 0.3), 3.0));
      setPan({ x: 0, y: 0 });
    }

    console.log("COMMIT CROP: SUCCESS");
    showToast("Crop applied to view. Original DSD remains intact.");
  };

  const handleCancelCrop = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setDraftCrop(null);
    setActiveTool('select');
  };

  // Text Annotation Commit
  const handleCommitText = () => {
    if (editingText && editingText.text.trim()) {
      let nextAnnos;
      if (editingText.id) {
        // Edit existing text annotation
        nextAnnos = annotations.map(a => a.id === editingText.id ? { ...a, text: editingText.text.trim() } : a);
      } else {
        // Create new text annotation
        const newAnno = {
          id: `anno_${Date.now()}`,
          type: 'text',
          x: editingText.srcX,
          y: editingText.srcY,
          text: editingText.text.trim(),
          color: selectedColor
        };
        nextAnnos = [...annotations, newAnno];
        setSelectedAnnoId(newAnno.id);
      }
      pushHistory(nextAnnos);
    }
    setEditingText(null);
  };

  // Compose Annotated Canvas for Clipboard & Download
  const generateAnnotatedCanvas = useCallback(() => {
    const img = imgRef.current;
    if (!img) return null;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    const srcX = appliedCrop ? appliedCrop.x : 0;
    const srcY = appliedCrop ? appliedCrop.y : 0;
    const srcW = appliedCrop ? appliedCrop.width : naturalSize.width;
    const srcH = appliedCrop ? appliedCrop.height : naturalSize.height;

    canvas.width = srcW;
    canvas.height = srcH;

    // 1. Draw base image slice
    ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, srcW, srcH);

    // 2. Draw annotations shifted by crop offset
    annotations.forEach(anno => {
      ctx.save();
      const localX = anno.x - srcX;
      const localY = anno.y - srcY;

      if (anno.type === 'highlight') {
        // Pure translucent rectangular fill (rgba(255,230,0,0.35))
        ctx.fillStyle = anno.color.bg;
        ctx.fillRect(localX, localY, anno.width, anno.height);
      } else if (anno.type === 'rectangle') {
        ctx.strokeStyle = anno.color.hex;
        ctx.lineWidth = 3;
        ctx.strokeRect(localX, localY, anno.width, anno.height);
      } else if (anno.type === 'arrow') {
        const x1 = anno.x1 - srcX;
        const y1 = anno.y1 - srcY;
        const x2 = anno.x2 - srcX;
        const y2 = anno.y2 - srcY;

        ctx.strokeStyle = anno.color.hex;
        ctx.fillStyle = anno.color.hex;
        ctx.lineWidth = 3;

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        const angle = Math.atan2(y2 - y1, x2 - x1);
        const headlen = 16;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headlen * Math.cos(angle - Math.PI / 6), y2 - headlen * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headlen * Math.cos(angle + Math.PI / 6), y2 - headlen * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
      } else if (anno.type === 'text') {
        ctx.font = '500 13px Inter, system-ui, -apple-system, sans-serif';
        const metrics = ctx.measureText(anno.text);
        const textPadX = 8;
        const boxW = Math.max(metrics.width + textPadX * 2, 60);
        const boxH = 26;

        // White semi-transparent box
        ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
        ctx.fillRect(localX, localY, boxW, boxH);
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 1;
        ctx.strokeRect(localX, localY, boxW, boxH);

        // Dark text
        ctx.fillStyle = '#0f172a';
        ctx.fillText(anno.text, localX + textPadX, localY + 18);
      }
      ctx.restore();
    });

    return canvas;
  }, [appliedCrop, naturalSize, annotations]);

  // Ctrl+C and Toolbar Copy: Copy Annotated Image to System Clipboard
  const handleCopyImageToClipboard = useCallback(async () => {
    const canvas = generateAnnotatedCanvas();
    if (!canvas) {
      showToast("Unable to copy image");
      return;
    }

    try {
      if (navigator.clipboard && typeof ClipboardItem !== 'undefined') {
        canvas.toBlob(async (blob) => {
          if (!blob) {
            showToast("Unable to copy image");
            return;
          }
          try {
            await navigator.clipboard.write([
              new ClipboardItem({ 'image/png': blob })
            ]);
            showToast("Annotated image copied to clipboard");
          } catch (clipErr) {
            console.error("Clipboard write error", clipErr);
            showToast("Image copy is not supported by this browser.");
          }
        }, 'image/png');
      } else {
        showToast("Image copy is not supported by this browser.");
      }
    } catch (err) {
      console.error("Copy failed", err);
      showToast("Unable to copy image");
    }
  }, [generateAnnotatedCanvas]);

  // Export Client-Side Derived Annotated Image Download
  const handleExportAnnotatedImage = () => {
    const canvas = generateAnnotatedCanvas();
    if (!canvas) return;

    const dataUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    const baseName = evidence?.test_case_id ? `annotated_${evidence.test_case_id}` : 'annotated_dsd_evidence';
    a.href = dataUrl;
    a.download = `${baseName}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    showToast("Exported annotated evidence image (derived).");
  };

  // Keyboard Shortcuts (Ctrl+C, Delete, Backspace, Esc, Ctrl+Z, Ctrl+Y, V, H, R, A, T, C)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // If user is editing in a textarea or input, preserve native behavior for Enter, Space, typing, text copy
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.key === 'Escape') {
          setEditingText(null);
        }
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
        e.preventDefault();
        handleCopyImageToClipboard();
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedAnnoId) {
          e.preventDefault();
          handleDeleteSelected();
        }
      } else if (e.key === 'Escape') {
        if (draftCrop) {
          setDraftCrop(null);
        } else if (selectedAnnoId) {
          setSelectedAnnoId(null);
        } else {
          onClose();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        if (e.shiftKey) handleRedo();
        else handleUndo();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        handleRedo();
      } else {
        if (e.key.toLowerCase() === 'v') setActiveTool('select');
        else if (e.key.toLowerCase() === 'h') setActiveTool('highlight');
        else if (e.key.toLowerCase() === 'r') setActiveTool('rectangle');
        else if (e.key.toLowerCase() === 'a') setActiveTool('arrow');
        else if (e.key.toLowerCase() === 't') setActiveTool('text');
        else if (e.key.toLowerCase() === 'c') setActiveTool('crop');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, draftCrop, selectedAnnoId, handleDeleteSelected, handleUndo, handleRedo, handleCopyImageToClipboard]);

  const pageDisplay = evidence?.page_display || (evidence?.source_pages?.length > 1 ? evidence.source_pages.join('–') : evidence?.page_number);
  const pageLabel = pageDisplay ? `Page ${pageDisplay}` : 'DSD Page';
  const sectionLabel = evidence?.section || 'Report Layout';
  const scopeLabel = evidence?.evidence_scope?.replace(/_/g, ' ') || '';

  return (
    <div className="fixed inset-0 z-[200] flex flex-col bg-slate-950/95 backdrop-blur-md text-slate-100 select-none overflow-hidden animate-in fade-in duration-200">
      
      {/* ── TOP HEADER ──────────────────────────────────────────────────────── */}
      <header className="h-auto min-h-12 py-2 px-3 sm:px-5 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2 shrink-0 z-20 shadow-md">
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap min-w-0">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/60 font-semibold text-xs tracking-wider uppercase">
            <Sparkles className="w-3.5 h-3.5" />
            {evidence?.evidence_type?.replace(/_/g, ' ') || 'Source DSD Snapshot'}
          </span>
          <div className="hidden sm:block h-4 w-px bg-slate-700 mx-1" />
          <h2 className="text-xs sm:text-sm font-semibold text-white truncate flex items-center gap-2">
            <span>{pageLabel} • {sectionLabel}</span>
            {scopeLabel && scopeLabel !== sectionLabel && (
              <span className="text-slate-400 font-normal text-xs">• {scopeLabel}</span>
            )}
          </h2>
          {isAnnotatedView && (
            <span className="hidden md:inline-flex ml-2 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[11px] font-medium items-center gap-1">
              <Layers className="w-3 h-3" /> Annotated View
            </span>
          )}
          {appliedCrop && (
            <button
              type="button"
              onClick={handleResetCropOnly}
              className="ml-2 px-2 py-0.5 rounded bg-amber-600/30 hover:bg-amber-600/50 text-amber-200 border border-amber-500/50 text-[11px] font-medium flex items-center gap-1 cursor-pointer transition-colors"
              title="Click to remove crop and view full DSD page"
            >
              <Scissors className="w-3 h-3" /> Reset Crop
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* Copy Image Button */}
          <button
            type="button"
            onClick={handleCopyImageToClipboard}
            className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md bg-blue-600/90 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm cursor-pointer"
            title="Copy annotated image to clipboard (Ctrl+C)"
          >
            <Copy className="w-3.5 h-3.5" />
            <span className="hidden xs:inline">Copy</span>
          </button>

          {/* Export Derived Image */}
          <button
            type="button"
            onClick={handleExportAnnotatedImage}
            className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md bg-emerald-800/80 hover:bg-emerald-700 text-emerald-100 border border-emerald-700 text-xs font-medium transition-colors shadow-sm cursor-pointer"
            title="Export derived annotated PNG image"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden xs:inline">Export</span>
          </button>

          <div className="h-5 w-px bg-slate-700 mx-0.5 sm:mx-1" />

          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
            title="Close Viewer (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* ── INTERACTIVE SNIPPING TOOLBAR ───────────────────────────────────── */}
      <div className="h-12 px-3 sm:px-5 bg-slate-900/90 border-b border-slate-800/80 flex items-center justify-between shrink-0 z-20 text-xs overflow-x-auto no-scrollbar gap-2 sm:gap-4">
        
        {/* Navigation & Zoom Tools */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setActiveTool('select')}
            className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md font-medium transition-all cursor-pointer ${
              activeTool === 'select' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-300 hover:bg-slate-800'
            }`}
            title="Select & Pan (V) - Click annotations to move/resize; drag empty space to pan"
          >
            <MousePointer className="w-3.5 h-3.5" />
            <span>Select</span>
          </button>

          <div className="h-4 w-px bg-slate-800 mx-1" />

          <button
            type="button"
            onClick={() => handleZoomChange(zoom - 0.2)}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-300 transition-colors cursor-pointer"
            title="Zoom Out (Ctrl -)"
          >
            <ZoomOut className="w-4 h-4" />
          </button>

          <span className="w-12 text-center font-mono font-semibold text-slate-200">
            {Math.round(zoom * 100)}%
          </span>

          <button
            type="button"
            onClick={() => handleZoomChange(zoom + 0.2)}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-300 transition-colors cursor-pointer"
            title="Zoom In (Ctrl +)"
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={handleFitScreen}
            className="px-2 py-1 rounded text-slate-300 hover:bg-slate-800 transition-colors cursor-pointer"
            title="Fit to Screen"
          >
            Fit Screen
          </button>

          <button
            type="button"
            onClick={handleFitWidth}
            className="px-2 py-1 rounded text-slate-300 hover:bg-slate-800 transition-colors cursor-pointer"
            title="Fit to Width"
          >
            Fit Width
          </button>

          <button
            type="button"
            onClick={() => handleZoomChange(1.0)}
            className="px-2 py-1 rounded text-slate-300 hover:bg-slate-800 transition-colors cursor-pointer"
            title="100% Original Size"
          >
            100%
          </button>
        </div>

        {/* Snipping & Annotation Tools */}
        <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-lg border border-slate-800">
          
          {/* Highlight Tool: Translucent Snipping Tool Marker (0.35 Opacity) */}
          <button
            type="button"
            onClick={() => { setActiveTool('highlight'); setSelectedAnnoId(null); }}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded font-semibold transition-all cursor-pointer ${
              activeTool === 'highlight' ? 'bg-amber-400 text-slate-950 shadow-md ring-1 ring-amber-300' : 'text-slate-300 hover:bg-slate-800'
            }`}
            title="Highlight Tool (H) - Drag rectangle over headers, fields, or rows for translucent highlight"
          >
            <Highlighter className="w-3.5 h-3.5" />
            <span>Highlight</span>
          </button>

          {/* Outline Rectangle Tool */}
          <button
            type="button"
            onClick={() => { setActiveTool('rectangle'); setSelectedAnnoId(null); }}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded font-medium transition-all cursor-pointer ${
              activeTool === 'rectangle' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-300 hover:bg-slate-800'
            }`}
            title="Rectangle Tool (R) - Draw outline box"
          >
            <Square className="w-3.5 h-3.5" />
            <span>Box</span>
          </button>

          {/* Arrow Tool */}
          <button
            type="button"
            onClick={() => { setActiveTool('arrow'); setSelectedAnnoId(null); }}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded font-medium transition-all cursor-pointer ${
              activeTool === 'arrow' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-300 hover:bg-slate-800'
            }`}
            title="Arrow Tool (A) - Point to element"
          >
            <ArrowUpRight className="w-3.5 h-3.5" />
            <span>Arrow</span>
          </button>

          {/* Text Tool */}
          <button
            type="button"
            onClick={() => { setActiveTool('text'); setSelectedAnnoId(null); }}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded font-medium transition-all cursor-pointer ${
              activeTool === 'text' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-300 hover:bg-slate-800'
            }`}
            title="Text Note Tool (T) - Click on image to add text label"
          >
            <Type className="w-3.5 h-3.5" />
            <span>Text</span>
          </button>

          {/* Crop Tool */}
          <button
            type="button"
            onClick={() => { setActiveTool('crop'); setSelectedAnnoId(null); }}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded font-medium transition-all cursor-pointer ${
              activeTool === 'crop' ? 'bg-amber-600 text-white shadow-sm' : 'text-slate-300 hover:bg-slate-800'
            }`}
            title="Crop Tool (C) - Drag rectangle over region to isolate"
          >
            <Crop className="w-3.5 h-3.5" />
            <span>Crop</span>
          </button>
        </div>

        {/* Color Palette & Actions */}
        <div className="flex items-center gap-3">
          {['highlight', 'rectangle', 'arrow', 'text'].includes(activeTool) && (
            <div className="flex items-center gap-1.5 bg-slate-950/60 px-2 py-1 rounded-lg border border-slate-800">
              {PALETTE.map(col => (
                <button
                  key={col.id}
                  type="button"
                  onClick={() => setSelectedColor(col)}
                  className={`w-4 h-4 rounded-full transition-transform cursor-pointer ${
                    selectedColor.id === col.id ? 'ring-2 ring-white scale-110' : 'opacity-70 hover:opacity-100'
                  }`}
                  style={{ backgroundColor: col.hex }}
                  title={`${col.name} highlight color`}
                />
              ))}
            </div>
          )}

          {selectedAnnoId && (
            <button
              type="button"
              onClick={handleDeleteSelected}
              className="inline-flex items-center gap-1 px-2 py-1 bg-red-900/60 hover:bg-red-800 text-red-200 border border-red-700/60 rounded text-xs font-semibold shadow transition-colors cursor-pointer"
              title="Delete Selected Annotation (Del / Backspace)"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete</span>
            </button>
          )}

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleUndo}
              disabled={historyIndex === 0}
              className="p-1.5 rounded hover:bg-slate-800 text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              title="Undo (Ctrl+Z)"
            >
              <Undo2 className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={handleRedo}
              disabled={historyIndex >= history.length - 1}
              className="p-1.5 rounded hover:bg-slate-800 text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              title="Redo (Ctrl+Y)"
            >
              <Redo2 className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-rose-400 hover:bg-rose-950/50 hover:text-rose-300 transition-colors ml-1 cursor-pointer"
              title="Reset View and Clear Saved Annotations"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>

        </div>
      </div>

      {/* ── CANVAS & VIEWER AREA ────────────────────────────────────────────── */}
      <div 
        ref={containerRef}
        className={`flex-1 relative overflow-hidden bg-slate-950 flex items-center justify-center select-none ${
          activeTool === 'select' 
            ? (isPanning ? 'cursor-grabbing' : 'cursor-default') 
            : 'cursor-crosshair'
        }`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
      >
        {/* Transformable Canvas Container */}
        <div
          ref={canvasRef}
          className="relative transition-transform duration-75 will-change-transform shadow-2xl rounded overflow-hidden"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            width: `${cropW}px`,
            height: `${cropH}px`,
          }}
        >
          {/* Base Immutable Source Image (Offset by cropX, cropY) */}
          <img
            ref={imgRef}
            src={imageUrl}
            alt="Authoritative DSD Evidence"
            onLoad={handleImageLoad}
            crossOrigin="anonymous"
            draggable={false}
            className="block select-none pointer-events-none rounded"
            style={{
              position: 'absolute',
              left: `-${cropX}px`,
              top: `-${cropY}px`,
              width: `${naturalSize.width}px`,
              height: `${naturalSize.height}px`,
              maxWidth: 'none',
              maxHeight: 'none',
            }}
          />

          {/* SVG Vector Annotations Layer (Mapped to Viewport 0..cropW, 0..cropH) */}
          <svg
            className="absolute inset-0 w-full h-full z-10 overflow-hidden"
            viewBox={`0 0 ${cropW} ${cropH}`}
            style={{ pointerEvents: 'auto' }}
          >
            <defs>
              {PALETTE.map(col => (
                <marker
                  key={col.id}
                  id={`arrowhead-${col.id}`}
                  markerWidth="10"
                  markerHeight="10"
                  refX="7"
                  refY="3.5"
                  orient="auto"
                >
                  <polygon points="0 0, 10 3.5, 0 7" fill={col.hex} />
                </marker>
              ))}
            </defs>

            {/* Committed Annotations with Centralized Coordinate Transformation */}
            {annotations.map(anno => {
              const isSelected = anno.id === selectedAnnoId;

              if (anno.type === 'highlight') {
                const disp = sourceToDisplayRect(anno);
                // Clipping check
                const isVisible = (
                  disp.x + disp.width > 0 &&
                  disp.x < cropW &&
                  disp.y + disp.height > 0 &&
                  disp.y < cropH
                );
                if (!isVisible) return null;

                return (
                  <g key={anno.id}>
                    {/* Snipping-Tool Translucent Yellow Highlight Box (0.35 opacity) */}
                    <rect
                      x={disp.x}
                      y={disp.y}
                      width={disp.width}
                      height={disp.height}
                      fill={anno.color.bg}
                      stroke={isSelected ? anno.color.border : 'none'}
                      strokeWidth={isSelected ? 1.5 : 0}
                      strokeDasharray={isSelected ? '4 2' : 'none'}
                      style={{ cursor: isSelected ? 'move' : 'pointer' }}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        setSelectedAnnoId(anno.id);
                        const { x, y } = getSourceCoords(e);
                        setActiveDrag({
                          mode: 'move',
                          annoId: anno.id,
                          startSrcX: x,
                          startSrcY: y,
                          origAnno: { ...anno }
                        });
                      }}
                    />

                    {/* Resize Handles for Selected Highlight */}
                    {isSelected && (
                      <g>
                        {/* Top-Left */}
                        <circle
                          cx={disp.x}
                          cy={disp.y}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.border}
                          strokeWidth="2"
                          style={{ cursor: 'nwse-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-nw',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                        {/* Top-Right */}
                        <circle
                          cx={disp.x + disp.width}
                          cy={disp.y}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.border}
                          strokeWidth="2"
                          style={{ cursor: 'nesw-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-ne',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                        {/* Bottom-Right */}
                        <circle
                          cx={disp.x + disp.width}
                          cy={disp.y + disp.height}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.border}
                          strokeWidth="2"
                          style={{ cursor: 'nwse-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-se',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                        {/* Bottom-Left */}
                        <circle
                          cx={disp.x}
                          cy={disp.y + disp.height}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.border}
                          strokeWidth="2"
                          style={{ cursor: 'nesw-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-sw',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                      </g>
                    )}
                  </g>
                );
              } else if (anno.type === 'rectangle') {
                const disp = sourceToDisplayRect(anno);
                const isVisible = (
                  disp.x + disp.width > 0 &&
                  disp.x < cropW &&
                  disp.y + disp.height > 0 &&
                  disp.y < cropH
                );
                if (!isVisible) return null;

                return (
                  <g key={anno.id}>
                    <rect
                      x={disp.x}
                      y={disp.y}
                      width={disp.width}
                      height={disp.height}
                      fill="none"
                      stroke={anno.color.hex}
                      strokeWidth={isSelected ? 4 : 3}
                      strokeDasharray={isSelected ? '4 2' : 'none'}
                      style={{ cursor: isSelected ? 'move' : 'pointer' }}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        setSelectedAnnoId(anno.id);
                        const { x, y } = getSourceCoords(e);
                        setActiveDrag({
                          mode: 'move',
                          annoId: anno.id,
                          startSrcX: x,
                          startSrcY: y,
                          origAnno: { ...anno }
                        });
                      }}
                    />

                    {/* Resize Handles for Selected Rectangle */}
                    {isSelected && (
                      <g>
                        <circle
                          cx={disp.x}
                          cy={disp.y}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.hex}
                          strokeWidth="2"
                          style={{ cursor: 'nwse-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-nw',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                        <circle
                          cx={disp.x + disp.width}
                          cy={disp.y}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.hex}
                          strokeWidth="2"
                          style={{ cursor: 'nesw-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-ne',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                        <circle
                          cx={disp.x + disp.width}
                          cy={disp.y + disp.height}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.hex}
                          strokeWidth="2"
                          style={{ cursor: 'nwse-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-se',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                        <circle
                          cx={disp.x}
                          cy={disp.y + disp.height}
                          r="5"
                          fill="#ffffff"
                          stroke={anno.color.hex}
                          strokeWidth="2"
                          style={{ cursor: 'nesw-resize' }}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            const { x, y } = getSourceCoords(e);
                            setActiveDrag({
                              mode: 'resize-sw',
                              annoId: anno.id,
                              startSrcX: x,
                              startSrcY: y,
                              origAnno: { ...anno }
                            });
                          }}
                        />
                      </g>
                    )}
                  </g>
                );
              } else if (anno.type === 'arrow') {
                const p1 = sourceToDisplayPoint(anno.x1, anno.y1);
                const p2 = sourceToDisplayPoint(anno.x2, anno.y2);

                return (
                  <line
                    key={anno.id}
                    x1={p1.x}
                    y1={p1.y}
                    x2={p2.x}
                    y2={p2.y}
                    stroke={anno.color.hex}
                    strokeWidth={isSelected ? 5 : 3.5}
                    markerEnd={`url(#arrowhead-${anno.color.id})`}
                    style={{ cursor: 'pointer' }}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      setSelectedAnnoId(anno.id);
                    }}
                  />
                );
              } else if (anno.type === 'text') {
                if (editingText && editingText.id === anno.id) return null;

                const p = sourceToDisplayPoint(anno.x, anno.y);
                const textPad = 8;
                const approxW = Math.max(anno.text.length * 8.5, 60);
                const approxH = 26;

                return (
                  <g
                    key={anno.id}
                    transform={`translate(${p.x}, ${p.y})`}
                    style={{ cursor: 'move' }}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      setSelectedAnnoId(anno.id);
                      const { x, y } = getSourceCoords(e);
                      setActiveDrag({
                        mode: 'move',
                        annoId: anno.id,
                        startSrcX: x,
                        startSrcY: y,
                        origAnno: { ...anno, width: approxW + textPad, height: approxH }
                      });
                    }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      setEditingText({ id: anno.id, srcX: anno.x, srcY: anno.y, text: anno.text });
                    }}
                  >
                    {/* Semi-transparent White Background Box */}
                    <rect
                      x={0}
                      y={0}
                      width={approxW + textPad}
                      height={approxH}
                      fill="rgba(255, 255, 255, 0.92)"
                      stroke={isSelected ? '#2563eb' : '#64748b'}
                      strokeWidth={isSelected ? 2 : 1}
                      rx="4"
                    />
                    {/* Dark Crisp Text */}
                    <text
                      x={textPad / 2}
                      y={18}
                      fill="#0f172a"
                      fontSize="13"
                      fontWeight="500"
                      fontFamily="Inter, system-ui, sans-serif"
                    >
                      {anno.text}
                    </text>
                  </g>
                );
              }
              return null;
            })}

            {/* Active Drawing Preview (Transformed to Viewport) */}
            {activeDrag && activeDrag.mode === 'draw' && (
              <g>
                {activeDrag.type === 'highlight' && (() => {
                  const pStart = sourceToDisplayPoint(activeDrag.startX, activeDrag.startY);
                  const pCurr = sourceToDisplayPoint(activeDrag.currentX, activeDrag.currentY);
                  return (
                    <rect
                      x={Math.min(pStart.x, pCurr.x)}
                      y={Math.min(pStart.y, pCurr.y)}
                      width={Math.abs(pCurr.x - pStart.x)}
                      height={Math.abs(pCurr.y - pStart.y)}
                      fill={activeDrag.color.bg}
                      stroke={activeDrag.color.border}
                      strokeWidth="1"
                      strokeDasharray="4 2"
                    />
                  );
                })()}
                {activeDrag.type === 'rectangle' && (() => {
                  const pStart = sourceToDisplayPoint(activeDrag.startX, activeDrag.startY);
                  const pCurr = sourceToDisplayPoint(activeDrag.currentX, activeDrag.currentY);
                  return (
                    <rect
                      x={Math.min(pStart.x, pCurr.x)}
                      y={Math.min(pStart.y, pCurr.y)}
                      width={Math.abs(pCurr.x - pStart.x)}
                      height={Math.abs(pCurr.y - pStart.y)}
                      fill="none"
                      stroke={activeDrag.color.hex}
                      strokeWidth="3"
                      strokeDasharray="6 4"
                    />
                  );
                })()}
                {activeDrag.type === 'arrow' && (() => {
                  const pStart = sourceToDisplayPoint(activeDrag.startX, activeDrag.startY);
                  const pCurr = sourceToDisplayPoint(activeDrag.currentX, activeDrag.currentY);
                  return (
                    <line
                      x1={pStart.x}
                      y1={pStart.y}
                      x2={pCurr.x}
                      y2={pCurr.y}
                      stroke={activeDrag.color.hex}
                      strokeWidth="3.5"
                      markerEnd={`url(#arrowhead-${activeDrag.color.id})`}
                    />
                  );
                })()}
              </g>
            )}
          </svg>

          {/* In-Place Text Editor Overlay (Transformed to Viewport) */}
          {editingText && (() => {
            const p = sourceToDisplayPoint(editingText.srcX, editingText.srcY);
            return (
              <div
                className="absolute z-40"
                style={{
                  left: `${p.x}px`,
                  top: `${p.y}px`,
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center gap-1 bg-white/95 border border-slate-600 rounded-md shadow-2xl p-1">
                  <input
                    ref={textInputRef}
                    type="text"
                    autoFocus
                    placeholder="Type note (Enter to save)..."
                    value={editingText.text}
                    onChange={(e) => setEditingText(prev => ({ ...prev, text: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleCommitText();
                      } else if (e.key === 'Escape') {
                        setEditingText(null);
                      }
                    }}
                    onBlur={handleCommitText}
                    className="bg-transparent border-none text-slate-900 text-xs px-2 py-1 font-medium focus:outline-none w-56 placeholder:text-slate-400"
                  />
                  <button
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); handleCommitText(); }}
                    className="p-1 bg-blue-600 hover:bg-blue-500 text-white rounded cursor-pointer"
                    title="Save Text (Enter)"
                  >
                    <Check className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })()}

          {/* Active Crop Overlay (Transformed to Viewport) */}
          {draftCrop && (() => {
            const cStart = sourceToDisplayPoint(
              draftCrop.startX !== undefined ? draftCrop.startX : draftCrop.x,
              draftCrop.startY !== undefined ? draftCrop.startY : draftCrop.y
            );
            const cCurr = sourceToDisplayPoint(
              draftCrop.currentX !== undefined ? draftCrop.currentX : draftCrop.x + draftCrop.width,
              draftCrop.currentY !== undefined ? draftCrop.currentY : draftCrop.y + draftCrop.height
            );
            const boxLeft = Math.min(cStart.x, cCurr.x);
            const boxTop = Math.min(cStart.y, cCurr.y);
            const boxW = Math.abs(cCurr.x - cStart.x);
            const boxH = Math.abs(cCurr.y - cStart.y);

            return (
              <div
                className="absolute border-2 border-amber-400 bg-amber-500/15 pointer-events-none z-30 shadow-2xl"
                style={{
                  left: `${boxLeft}px`,
                  top: `${boxTop}px`,
                  width: `${boxW}px`,
                  height: `${boxH}px`,
                }}
              >
                <div className="absolute -top-1.5 -left-1.5 w-3 h-3 bg-amber-400 border border-black rounded-sm" />
                <div className="absolute -top-1.5 -right-1.5 w-3 h-3 bg-amber-400 border border-black rounded-sm" />
                <div className="absolute -bottom-1.5 -left-1.5 w-3 h-3 bg-amber-400 border border-black rounded-sm" />
                <div className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-amber-400 border border-black rounded-sm" />
              </div>
            );
          })()}

        </div>

        {/* Floating Crop Confirmation Action Bar */}
        {draftCrop && draftCrop.isReady && (
          <div 
            className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40 bg-slate-900/95 border border-slate-700 px-4 py-2 rounded-xl shadow-2xl flex items-center gap-4 text-xs select-none"
            onPointerDown={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            <span className="font-mono text-amber-300 font-semibold">
              Crop: {Math.round(draftCrop.width)} × {Math.round(draftCrop.height)} px
            </span>
            <button
              type="button"
              onClick={handleApplyCrop}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg shadow cursor-pointer transition-colors"
            >
              <Check className="w-4 h-4" /> Apply Crop
            </button>
            <button
              type="button"
              onClick={handleCancelCrop}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" /> Cancel
            </button>
          </div>
        )}

      </div>

      {/* ── FOOTER & STATUS BAR ────────────────────────────────────────────── */}
      <footer className="h-9 px-5 bg-slate-900 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 shrink-0 z-20">
        <div className="flex items-center gap-4">
          <span>Dimensions: <strong className="text-slate-200 font-mono">{naturalSize.width} × {naturalSize.height} px</strong></span>
          {appliedCrop && (
            <span className="flex items-center gap-2">
              <span>Crop Area: <strong className="text-amber-300 font-mono">{appliedCrop.width} × {appliedCrop.height} px</strong></span>
              <button
                type="button"
                onClick={handleResetCropOnly}
                className="text-amber-400 hover:text-amber-300 underline cursor-pointer"
              >
                Reset Crop
              </button>
            </span>
          )}
          <span>Annotations: <strong className="text-slate-200">{annotations.length}</strong></span>
        </div>

        <div className="flex items-center gap-4 text-slate-400">
          <span>Copy Image: <strong>Ctrl + C</strong></span>
          <span>Zoom: <strong>Ctrl + Wheel</strong></span>
          <span>Shortcuts: <strong>H (Highlight) • T (Text) • V (Select) • Del (Delete) • Ctrl+Z (Undo)</strong></span>
        </div>
      </footer>

      {/* Toast Feedback */}
      {toastMessage && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-50 bg-slate-900 border border-slate-700 text-slate-100 text-xs px-4 py-2 rounded-lg shadow-2xl flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
          <Check className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

    </div>
  );
}
