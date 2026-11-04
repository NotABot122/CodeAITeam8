// The block workspace. Loaded lazily (Blockly is large) only when a student picks Blocks.
import {Box} from '@mui/material';
import * as Blockly from 'blockly/core';
import {useEffect, useRef} from 'react';

import {defineBlocks} from './defs';
import type {WorkspaceState} from './format';
import {workspaceToPython, type Generated} from './python';
import {TOOLBOX} from './toolbox';

interface Props {
  /** What to show at first; null starts empty. Remount (change `key`) to load something else. */
  initial: WorkspaceState | null;
  /** Called after every edit. `changed` is false until the code differs from what was loaded,
   *  so switching modes without editing leaves the student's text exactly as they wrote it. */
  onChange: (generated: Generated, changed: boolean) => void;
  dark: boolean;
}

const DARK = 'codeai-dark';

function theme(dark: boolean): Blockly.Theme {
  if (!dark) return Blockly.Themes.Classic;
  return Blockly.registry.getObject(Blockly.registry.Type.THEME, DARK) as Blockly.Theme | null ?? Blockly.Theme.defineTheme(DARK, {
    name: DARK,
    base: Blockly.Themes.Classic,
    componentStyles: {
      workspaceBackgroundColour: '#1b1b27', toolboxBackgroundColour: '#12121a', toolboxForegroundColour: '#e6e6f0',
      flyoutBackgroundColour: '#252536', flyoutForegroundColour: '#e6e6f0', flyoutOpacity: 0.95,
      scrollbarColour: '#6d6d80', insertionMarkerColour: '#ffffff', cursorColour: '#d0d0d0',
    },
  });
}

export default function BlockEditor({initial, onChange, dark}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const workspace = useRef<Blockly.WorkspaceSvg | null>(null);
  const report = useRef(onChange);
  report.current = onChange;

  useEffect(() => {
    defineBlocks();
    const ws = Blockly.inject(host.current!, {
      toolbox: TOOLBOX,
      toolboxPosition: 'start',
      renderer: 'zelos',
      theme: theme(dark),
      trashcan: true,
      comments: true,
      disable: false,  // a disabled block would silently drop out of the code
      sounds: false,
      move: {scrollbars: true, drag: true, wheel: true},
      zoom: {controls: true, wheel: false, startScale: 0.8, maxScale: 2, minScale: 0.4, scaleSpeed: 1.15},
    });
    workspace.current = ws;
    if (initial) Blockly.serialization.workspaces.load(initial, ws);
    const save = () => Blockly.serialization.workspaces.save(ws) as WorkspaceState;
    const baseline = workspaceToPython(save()).code;
    let changed = false;
    report.current(workspaceToPython(save()), false);
    const listener = (e: Blockly.Events.Abstract) => {
      if (e.isUiEvent || ws.isDragging()) return;
      const generated = workspaceToPython(save());
      changed ||= generated.code !== baseline;
      report.current(generated, changed);
    };
    ws.addChangeListener(listener);
    const resize = new ResizeObserver(() => Blockly.svgResize(ws));
    resize.observe(host.current!);
    return () => {
      resize.disconnect();
      ws.removeChangeListener(listener);
      ws.dispose();
      workspace.current = null;
    };
    // `initial` is read once per mount on purpose; the parent remounts with a new key to reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { workspace.current?.setTheme(theme(dark)); }, [dark]);

  return (
    <Box sx={{position: 'relative', flex: '1 0 360px', minHeight: 360, border: 1, borderColor: 'divider', borderRadius: '8px', overflow: 'hidden'}}>
      <Box ref={host} role="application" aria-label="Block workspace" sx={{position: 'absolute', inset: 0}} />
    </Box>
  );
}
