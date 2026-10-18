import { useState } from 'react';

const WORKSPACES_KEY = 'dhaka-evcs-workspaces';

function readSavedWorkspaces() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(WORKSPACES_KEY) || '[]');
    return Array.isArray(saved) ? saved.filter(item => item && typeof item.name === 'string' && item.state) : [];
  } catch {
    return [];
  }
}

export function useWorkspace() {
  const [workspaceName, setWorkspaceName] = useState('');
  const [savedWorkspaces, setSavedWorkspaces] = useState(readSavedWorkspaces);
  const [workspaceNotice, setWorkspaceNotice] = useState('');
  const [selectedWorkspace, setSelectedWorkspace] = useState('');

  const save = (getState) => {
    const name = workspaceName.trim();
    if (!name) {
      setWorkspaceNotice('Enter a workspace name before saving.');
      return;
    }
    const next = [...savedWorkspaces.filter(item => item.name !== name), { name, state: getState() }]
      .sort((left, right) => left.name.localeCompare(right.name));
    try {
      window.localStorage.setItem(WORKSPACES_KEY, JSON.stringify(next));
      setSavedWorkspaces(next);
      setSelectedWorkspace(name);
      setWorkspaceNotice(`Saved “${name}”`);
    } catch (saveError) {
      setWorkspaceNotice(`Workspace could not be saved: ${saveError.message}`);
    }
  };

  const load = (name, applyState) => {
    const workspace = savedWorkspaces.find(item => item.name === name);
    if (!workspace) return;
    applyState(workspace.state);
    setSelectedWorkspace(name);
    setWorkspaceNotice(`Loaded "${name}".`);
  };

  const remove = () => {
    const next = savedWorkspaces.filter(item => item.name !== selectedWorkspace);
    try {
      window.localStorage.setItem(WORKSPACES_KEY, JSON.stringify(next));
      setSavedWorkspaces(next);
      setWorkspaceNotice(`Deleted "${selectedWorkspace}".`);
      setSelectedWorkspace('');
    } catch (saveError) {
      setWorkspaceNotice(`Workspace could not be deleted: ${saveError.message}`);
    }
  };

  return {
    workspaceName,
    setWorkspaceName,
    savedWorkspaces,
    workspaceNotice,
    selectedWorkspace,
    setSelectedWorkspace,
    save,
    load,
    remove,
  };
}
