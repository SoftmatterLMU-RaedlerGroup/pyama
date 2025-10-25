'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  FolderTree, 
  FileText, 
  Sparkles, 
  FlaskConical,
  GitMerge,
  Settings 
} from 'lucide-react';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  description: string;
}

const navItems: NavItem[] = [
  {
    label: 'File Explorer',
    href: '/test/file-explorer',
    icon: <FolderTree className="w-5 h-5" />,
    description: 'Browse directories and files'
  },
  {
    label: 'File Information',
    href: '/test/file-info',
    icon: <FileText className="w-5 h-5" />,
    description: 'Load metadata & view features'
  },
  {
    label: 'Workflow',
    href: '/test/workflow',
    icon: <FlaskConical className="w-5 h-5" />,
    description: 'Run processing workflow'
  },
  {
    label: 'Merge',
    href: '/test/merge',
    icon: <GitMerge className="w-5 h-5" />,
    description: 'Merge FOVs into samples'
  },
  {
    label: 'Analysis',
    href: '/test/analysis',
    icon: <FlaskConical className="w-5 h-5" />,
    description: 'Fit models to trace data'
  },
];

export default function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="w-64 bg-white border-r border-gray-200 min-h-screen p-4">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">PyAMA</h2>
        <p className="text-xs text-gray-500">API Testing Interface</p>
      </div>

      <div className="space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-start gap-3 px-3 py-2 rounded-lg transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <div className={`mt-0.5 ${isActive ? 'text-blue-600' : 'text-gray-500'}`}>
                {item.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className={`text-sm font-medium ${isActive ? 'text-blue-900' : 'text-gray-900'}`}>
                  {item.label}
                </div>
                <div className={`text-xs mt-0.5 ${isActive ? 'text-blue-600' : 'text-gray-500'}`}>
                  {item.description}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      <div className="mt-8 pt-6 border-t border-gray-200">
        <div className="text-xs text-gray-500">
          <p className="font-medium text-gray-700 mb-2">Backend:</p>
          <p className="text-xs">localhost:8000</p>
        </div>
      </div>
    </nav>
  );
}

