# PyAMA Frontend Demo

This document provides a step-by-step guide to test the PyAMA frontend application.

## Prerequisites

1. **Backend Server**: PyAMA backend must be running on `http://localhost:8000`
2. **Sample Files**: Have some ND2 or CZI files available for testing

## Quick Start

### 1. Start the Backend Server

```bash
# In one terminal
cd pyama-backend
uv run python -m pyama_backend
```

### 2. Start the Frontend

```bash
# In another terminal
cd pyama-frontend
npm run dev
```

### 3. Open the Application

Navigate to `http://localhost:3000` in your browser.

## Testing the File Explorer

### Basic Navigation

1. **Browse Directories**: Click on folder icons to navigate through directories
2. **File Selection**: Click on file names to select them
3. **File Types**: The explorer shows different icons for:
   - 📁 Directories (blue folder icon)
   - 🔬 Microscopy files (.nd2, .czi) - green file icon
   - 📄 Other files - gray file icon

### Search Functionality

1. **Enable Search**: Click the search icon (🔍) in the file explorer header
2. **Search for Files**: Type in the search box to find files by name
3. **Filter Results**: Only microscopy files (.nd2, .czi) are shown in search results

### Load Metadata

1. **Select a File**: Click on a .nd2 or .czi file
2. **Load Button**: The load button will become active
3. **Click Load**: Click "Load Metadata" to extract file information
4. **View Results**: Metadata will be displayed in the right panel

## Expected Behavior

### File Explorer Panel (Left)
- Shows current directory path
- Lists files and folders with appropriate icons
- Supports navigation by clicking on folders
- Search functionality for finding microscopy files
- Refresh button to reload current directory

### Load Button Panel (Top Right)
- Shows selected file information
- Load button is only active for microscopy files
- Status indicators for loading, success, and errors
- Help text when no file is selected

### Metadata Display Panel (Bottom Right)
- Shows detailed file information when loaded
- Organized sections for different metadata types
- Raw JSON metadata at the bottom
- Loading and error states

## Troubleshooting

### Backend Connection Issues

**Symptom**: "Backend Disconnected" message at the top
**Solution**: 
1. Ensure backend is running on port 8000
2. Check if `http://localhost:8000/health` returns `{"status": "healthy"}`

### File Loading Issues

**Symptom**: "Load Failed" error message
**Solutions**:
1. Ensure the file is a valid .nd2 or .czi file
2. Check that the file path is accessible by the backend
3. Verify the file is not corrupted

### Search Not Working

**Symptom**: No search results or search not responding
**Solutions**:
1. Ensure backend is running
2. Try searching in a directory that contains microscopy files
3. Check browser console for error messages

## Sample Test Files

If you don't have microscopy files, you can test with:

1. **Any .nd2 or .czi files** - Will show full metadata
2. **Other file types** - Will show file info but no metadata preview
3. **Directories** - Will show directory contents

## Features Demonstrated

✅ **File System Navigation** - Browse directories and files  
✅ **File Type Detection** - Distinguish between file types  
✅ **Search Functionality** - Find files by name pattern  
✅ **Metadata Extraction** - Load and display microscopy metadata  
✅ **Error Handling** - Graceful error states and messages  
✅ **Loading States** - Visual feedback during operations  
✅ **Responsive Design** - Works on different screen sizes  
✅ **Backend Integration** - Real-time communication with PyAMA backend  

## Next Steps

After testing the basic functionality, you can:

1. **Add More File Types** - Extend support for other microscopy formats
2. **Enhanced Search** - Add filters for file size, date, etc.
3. **File Preview** - Show thumbnail images of microscopy files
4. **Batch Operations** - Select and process multiple files
5. **Export Metadata** - Save metadata to files
6. **Advanced Filtering** - Filter by experiment parameters