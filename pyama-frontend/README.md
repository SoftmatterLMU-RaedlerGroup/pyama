# PyAMA Frontend

A Next.js frontend application for browsing and loading microscopy files with the PyAMA backend.

## Features

- **File Explorer**: Browse directories and search for microscopy files (.nd2, .czi)
- **File Selection**: Click to select microscopy files
- **Metadata Loading**: Load and display detailed metadata from microscopy files
- **Real-time Status**: Backend connection status and loading indicators
- **Responsive Design**: Works on desktop and mobile devices

## Prerequisites

- Node.js 18+ 
- PyAMA Backend running on `http://localhost:8000`

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Start the Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:3000`.

### 3. Start the Backend Server

Make sure the PyAMA backend is running:

```bash
cd ../pyama-backend
uv run python -m pyama_backend
```

## Usage

1. **Browse Files**: Use the file explorer on the left to navigate directories
2. **Search Files**: Click the search icon to search for microscopy files
3. **Select File**: Click on a .nd2 or .czi file to select it
4. **Load Metadata**: Click the "Load Metadata" button to extract file metadata
5. **View Details**: The metadata will be displayed with detailed information

## Components

- **FileExplorer**: Directory browsing and file search
- **LoadButton**: File selection and metadata loading
- **MetadataDisplay**: Detailed metadata visualization

## API Integration

The frontend communicates with the PyAMA backend through these endpoints:

- `POST /api/v1/processing/list-directory` - List directory contents
- `POST /api/v1/processing/search-files` - Search for files
- `POST /api/v1/processing/file-info` - Get file information
- `POST /api/v1/processing/load-metadata` - Load microscopy metadata

## Configuration

Set the backend URL in `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## Development

```bash
# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run linting
npm run lint
```

## Troubleshooting

### Backend Connection Issues

If you see "Backend Disconnected":

1. Make sure the PyAMA backend is running on `http://localhost:8000`
2. Check that the backend server is accessible
3. Verify the `NEXT_PUBLIC_API_BASE_URL` in `.env.local`

### File Loading Issues

- Ensure the selected file is a supported format (.nd2 or .czi)
- Check that the file path is accessible by the backend server
- Verify the file is not corrupted

## Tech Stack

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **Lucide React** - Icons