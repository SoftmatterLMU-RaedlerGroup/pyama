'use client';

import React from 'react';

interface Endpoint {
  method: string;
  path: string;
}

interface TestingEndpointsProps {
  endpoints: Endpoint[];
}

export function TestingEndpoints({ endpoints }: TestingEndpointsProps) {
  return (
    <div className="p-3 bg-muted rounded-lg border">
      <div className="text-xs font-medium text-muted-foreground mb-2">
        Testing Endpoints:
      </div>
      <div className="space-y-1 text-sm">
        {endpoints.map((endpoint) => (
          <div key={`${endpoint.method}-${endpoint.path}`}>
            •{' '}
            <code className="bg-background px-2 py-1 rounded border">
              {endpoint.method} {endpoint.path}
            </code>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TestingEndpoints;
