'use client';

import React, { useState, useEffect } from 'react';
import { 
  Folder, 
  File, 
  ChevronRight, 
  ChevronDown, 
  Search, 
  RefreshCw,
  Loader2,
  AlertCircle
} from 'lucide-react';
import type { FileItem, DirectoryListingResponse, SearchFilesResponse } from '@/types/api';
import { PyamaApiService } from '@/lib/api';

interface FileExplorerProps {
  onFileSelect: (file: FileItem) => void;
  selectedFile?: FileItem | null;
}

export default function FileExplorer({ onFileSelect, selectedFile }: FileExplorerProps) {
  const [currentPath, setCurrentPath] = useState('/home');
  const [items, setItems] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<FileItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [pathInput, setPathInput] = useState('');
  const [showPathInput, setShowPathInput] = useState(false);
  const [showQuickNav, setShowQuickNav] = useState(false);

  // Common directories for quick navigation
  const quickNavDirs = [
    { name: 'Home', path: '/home' },
    { name: 'Root', path: '/' },
    { name: 'Desktop', path: '/home/jack/Desktop' },
    { name: 'Downloads', path: '/home/jack/Downloads' },
    { name: 'Documents', path: '/home/jack/Documents' },
    { name: 'Current Project', path: '/home/jack/workspace/pyama' },
  ];

  // Load directory contents
  const loadDirectory = async (path: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response: DirectoryListingResponse = await PyamaApiService.listDirectory({
        directory_path: path,
        include_hidden: false,
        filter_extensions: ['.nd2', '.czi', '.txt', '.py', '.json'] // Include common file types
      });

      if (response.success) {
        setItems(response.items);
        setCurrentPath(path);
      } else {
        setError(response.error || 'Failed to load directory');
      }
    } catch (err) {
      setError('Failed to connect to backend server');
      console.error('Error loading directory:', err);
    } finally {
      setLoading(false);
    }
  };

  // Search for files
  const searchFiles = async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    setError(null);

    try {
      const response: SearchFilesResponse = await PyamaApiService.searchFiles({
        search_path: currentPath,
        pattern: `**/*${query}*`,
        extensions: ['.nd2', '.czi'],
        max_depth: 5,
        include_hidden: false
      });

      if (response.success) {
        setSearchResults(response.files);
      } else {
        setError(response.error || 'Search failed');
      }
    } catch (err) {
      setError('Search failed');
      console.error('Error searching files:', err);
    } finally {
      setIsSearching(false);
    }
  };

  // Handle directory navigation
  const handleDirectoryClick = (item: FileItem) => {
    if (item.is_directory) {
      loadDirectory(item.path);
    } else if (item.is_file) {
      onFileSelect(item);
    }
  };

  // Handle search input
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    
    if (query.trim()) {
      searchFiles(query);
    } else {
      setSearchResults([]);
    }
  };

  // Handle path input
  const handlePathInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPathInput(e.target.value);
  };

  const handlePathSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedPath = pathInput.trim();
    if (trimmedPath) {
      loadDirectory(trimmedPath);
      setPathInput('');
      setShowPathInput(false);
    }
  };

  const handlePathInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setShowPathInput(false);
      setPathInput('');
    }
  };

  // Navigate to parent directory
  const navigateToParent = () => {
    const pathParts = currentPath.split('/').filter(part => part);
    if (pathParts.length > 0) {
      pathParts.pop(); // Remove last part
      const parentPath = '/' + pathParts.join('/');
      if (parentPath !== currentPath) {
        loadDirectory(parentPath);
      }
    }
  };

  // Generate breadcrumb navigation
  const getBreadcrumbs = () => {
    const pathParts = currentPath.split('/').filter(part => part);
    const breadcrumbs = [];
    
    for (let i = 0; i < pathParts.length; i++) {
      const path = '/' + pathParts.slice(0, i + 1).join('/');
      breadcrumbs.push({
        name: pathParts[i],
        path: path,
        isLast: i === pathParts.length - 1
      });
    }
    
    return breadcrumbs;
  };

  // Format file size
  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return '';
    
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  // Format modification time
  const formatModifiedTime = (timestamp?: string): string => {
    if (!timestamp) return '';
    
    try {
      const date = new Date(parseFloat(timestamp) * 1000);
      return date.toLocaleString();
    } catch {
      return '';
    }
  };

  // Get file icon
  const getFileIcon = (item: FileItem) => {
    if (item.is_directory) {
      return <Folder className="w-5 h-5 text-blue-500" />;
    }
    
    const ext = item.extension?.toLowerCase();
    if (ext === '.nd2' || ext === '.czi') {
      return <File className="w-5 h-5 text-green-500" />;
    }
    
    return <File className="w-5 h-5 text-gray-500" />;
  };

  // Load initial directory
  useEffect(() => {
    loadDirectory('/home');
  }, []);

  // Update path input when current path changes
  useEffect(() => {
    if (!showPathInput) {
      setPathInput(currentPath);
    }
  }, [currentPath, showPathInput]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + K to open path input
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setShowPathInput(true);
      }
      // Ctrl/Cmd + F to toggle search
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        setShowSearch(!showSearch);
      }
      // Escape to close modals
      if (e.key === 'Escape') {
        setShowPathInput(false);
        setShowQuickNav(false);
        setShowSearch(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showSearch]);

  const displayItems = showSearch ? searchResults : items;

  return (
    <div className="flex flex-col h-full bg-white border border-gray-200 rounded-lg">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">File Explorer</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setShowPathInput(!showPathInput)}
              className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
              title="Enter path manually (Ctrl+K)"
            >
              <Folder className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowQuickNav(!showQuickNav)}
              className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
              title="Quick navigation"
            >
              <ChevronDown className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowSearch(!showSearch)}
              className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
              title="Toggle search (Ctrl+F)"
            >
              <Search className="w-4 h-4" />
            </button>
            <button
              onClick={() => loadDirectory(currentPath)}
              disabled={loading}
              className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Path input */}
        {showPathInput && (
          <div className="mb-4">
            <form onSubmit={handlePathSubmit}>
              <input
                type="text"
                placeholder="Enter directory path..."
                value={pathInput}
                onChange={handlePathInputChange}
                onKeyDown={handlePathInputKeyDown}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
              <div className="mt-1 text-xs text-gray-500">
                Press Enter to navigate • Press Escape to cancel
              </div>
            </form>
          </div>
        )}

        {/* Search bar */}
        {showSearch && (
          <div className="mb-4">
            <input
              type="text"
              placeholder="Search for ND2/CZI files..."
              value={searchQuery}
              onChange={handleSearchChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        {/* Quick navigation */}
        {showQuickNav && (
          <div className="mb-4 p-3 bg-gray-50 rounded-md">
            <div className="text-sm font-medium text-gray-700 mb-2">Quick Navigation</div>
            <div className="flex flex-wrap gap-2">
              {quickNavDirs.map((dir) => (
                <button
                  key={dir.path}
                  onClick={() => {
                    loadDirectory(dir.path);
                    setShowQuickNav(false);
                  }}
                  className="px-3 py-1 text-xs bg-white border border-gray-300 rounded-md hover:bg-gray-100 hover:border-gray-400"
                  title={dir.path}
                >
                  {dir.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Current path and breadcrumbs */}
        <div className="text-sm text-gray-600 mb-2">
          <span className="font-medium">Path:</span> 
          {showPathInput ? (
            <span className="ml-1 text-gray-400">Enter path above</span>
          ) : (
            <div className="flex items-center gap-1 mt-1">
              <button
                onClick={() => loadDirectory('/')}
                className="text-blue-600 hover:text-blue-800 hover:underline"
                title="Go to root"
              >
                /
              </button>
              {getBreadcrumbs().map((crumb, index) => (
                <React.Fragment key={crumb.path}>
                  <span className="text-gray-400">/</span>
                  {crumb.isLast ? (
                    <span className="font-mono text-gray-800">{crumb.name}</span>
                  ) : (
                    <button
                      onClick={() => loadDirectory(crumb.path)}
                      className="text-blue-600 hover:text-blue-800 hover:underline"
                      title={`Go to ${crumb.path}`}
                    >
                      {crumb.name}
                    </button>
                  )}
                </React.Fragment>
              ))}
              {currentPath !== '/' && (
                <button
                  onClick={navigateToParent}
                  className="ml-2 px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                  title="Go to parent directory"
                >
                  ↑ Parent
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-md mb-4">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-700">{error}</span>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            <span className="ml-2 text-gray-600">Loading...</span>
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-1">
            {displayItems.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {showSearch ? 'No files found' : 'No items in this directory'}
              </div>
            ) : (
              displayItems.map((item, index) => (
                <div
                  key={`${item.path}-${index}`}
                  onClick={() => handleDirectoryClick(item)}
                  className={`flex items-center gap-3 p-3 rounded-md cursor-pointer transition-colors ${
                    selectedFile?.path === item.path
                      ? 'bg-blue-100 border border-blue-300'
                      : 'hover:bg-gray-100'
                  }`}
                >
                  {getFileIcon(item)}
                  
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 truncate">
                      {item.name}
                    </div>
                    <div className="text-sm text-gray-500">
                      {item.is_directory ? 'Directory' : formatFileSize(item.size_bytes)}
                      {item.modified_time && (
                        <span className="ml-2">
                          • {formatModifiedTime(item.modified_time)}
                        </span>
                      )}
                    </div>
                  </div>

                  {item.is_directory && (
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {isSearching && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
            <span className="ml-2 text-gray-600">Searching...</span>
          </div>
        )}
      </div>

      {/* Help text */}
      <div className="p-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
        <div className="flex items-center justify-between">
          <span>Click folders to navigate • Click files to select</span>
          <div className="flex gap-3">
            <span>Ctrl+K: Enter path</span>
            <span>Ctrl+F: Search</span>
            <span>Esc: Close</span>
          </div>
        </div>
      </div>
    </div>
  );
}