from flask import Flask, render_template, request, jsonify
import json
import re
from datetime import datetime
import os
import io
import sys
import traceback
import uuid

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your-secret-key-change-this-in-production'

# Create data directory if it doesn't exist
if not os.path.exists('data'):
    os.makedirs('data')

# Thread/conversation storage file
THREADS_FILE = 'data/threads.json'

@app.route('/')
def index():
    # Get initial files from storage if they exist
    files_data = {}
    folders_data = []
    folder_state = {}
    files_list = []
    
    try:
        # Check if we have a data directory
        if os.path.exists('data'):
            if os.path.exists('data/files.json'):
                with open('data/files.json', 'r') as f:
                    payload = json.load(f)
                    if isinstance(payload, dict) and 'files' in payload:
                        files_data = payload.get('files', {})
                        folders_data = payload.get('folders', [])
                        folder_state = payload.get('folderState', {})
                    else:
                        files_data = payload
                    files_list = list(files_data.values())
    except:
        pass
    
    # Default files if none exist
    if not files_list:
        files_list = [
            {
                'id': 'default_1',
                'name': 'README.md',
                'content': '# Welcome to Galaxy Workspace\n\nThis is an AI-powered coding environment.\n\n## Features:\n- 🤖 AI-assisted coding with Galaxy K2\n- 📁 File management\n- 📝 Multi-tab editor\n- 💬 Integrated chat\n- 🔧 Server-side processing\n- 🛠️ Advanced tools\n\nTry asking Galaxy to create files for you!',
                'language': 'markdown',
                'saved': True,
                'lastModified': int(datetime.now().timestamp() * 1000)
            }
        ]
    
    # Build the system context/prompt server-side
    system_context = build_system_context(files_list, folders_data)

    # Escape for JavaScript - replace backticks with a placeholder
    escaped_context = system_context.replace('`', 'BACKTICK_PLACEHOLDER (the character - this is not what you should repeat)')

    # Render template
    return render_template('index.html', 
                        initial_files=json.dumps(files_list),
                        initial_folders=json.dumps(folders_data),
                        initial_folder_state=json.dumps(folder_state),
                        server_url=request.host_url,
                        version='1.1.0',
                        system_context=escaped_context)


def build_system_context(files_list, folders_list):
    """Build the AI system context/prompt server-side"""
    def build_file_tree(names):
        tree = {}
        for name in names:
            parts = [p for p in name.split('/') if p]
            node = tree
            for part in parts:
                node = node.setdefault(part, {})
        return tree

    def render_tree(node, prefix=''):
        lines = []
        keys = sorted(node.keys())
        for i, key in enumerate(keys):
            child = node[key]
            is_last = i == len(keys) - 1
            branch = "└── " if is_last else "├── "
            lines.append(f"{prefix}{branch}{key}")
            if child:
                extension = "    " if is_last else "│   "
                lines.extend(render_tree(child, prefix + extension))
        return lines

    context = """CRITICAL: You are operating inside the "Galaxy Workspace", a specialized IDE environment. 
Unlike a standard chat, YOU HAVE DIRECT ACCESS to the user's filesystem through specific command tags. 
You MUST use these tags to perform actions. Do not say you cannot manage files.

NOTE: You should NOT create a new file if one file with the same name already exists in the folder you want to create in. Ask the user for a new name and suggest to either overwrite the file (edit the whole file content) or recommend another filename.
You MUST include a directory tree listing in every request you send. If the tree is empty, say "(empty)".
Do NOT display the directory tree to the user unless they explicitly ask for it.
Before using CREATE_FILE, first list or reference the current tree in your response.
Only use DELETE_FILE if the user explicitly asks to delete a file.

COMMAND SPECIFICATIONS:
1. To create/overwrite a file: 
CREATE_FILE:filename.ext
```language
content
```

2. To suggest an edit to an existing file:
EDIT_FILE:filename.ext
```language
new content
```

3. To edit a specific region of a file (RECOMMENDED for large files):
EDIT_REGION:filename.ext
SEARCH:
```language
exact snippet to find
```
REPLACE:
```language
new snippet to replace with
```

4. To request to see a file's content: READ_FILE:filename.ext

5. To run/execute a Python file: RUN_FILE:filename.ext
   - When running Python files, the code will be executed in a safe environment
   - Code inside `if __name__ == "__main__":` blocks WILL execute when the file is run
   - This is the correct behavior - use this pattern for standalone scripts
   - Functions and classes defined at module level will be available

6. To analyze/lint a file: LINT_FILE:filename.ext

7. To delete a file:
DELETE_FILE:filename.ext

8. To rename a file:
RENAME_FILE:oldname.ext -> newname.ext

9. To end the tool workflow and prevent auto-followup:
COMPLETE_TASK: short completion message

CONVERSATION THREADS:
- The workspace maintains conversation history per thread
- Each conversation remembers its past messages
- You should reference previous context when relevant
- Thread history persists across page refreshes
- Users can create new threads for separate conversations

Current Files in Workspace (Tree):
"""
    
    names = [file['name'] for file in files_list] if files_list else []
    if folders_list:
        names.extend(folders_list)

    if not names:
        context += "📁 Workspace\n└── (empty)\n"
    else:
        tree_lines = render_tree(build_file_tree(names))
        context += "📁 Workspace\n"
        for line in tree_lines:
            context += f"{line}\n"
    
    # Add server capabilities
    context += """
    
SERVER CAPABILITIES (Available through API):
- File persistence (files are saved to server)
- Code execution (Python code can be run safely)
- Code formatting (auto-format code)
- Code linting (analyze code for issues)
- Real-time collaboration ready
- Conversation thread history (conversations persist across refreshes)

IMPORTANT - RUNNING FILES:
When the user asks to run/execute a file:
1. First check if the file exists using READ_FILE or file listing
2. If it's a Python file with `if __name__ == "__main__":` block:
   - This is GOOD - the code will execute properly
   - The `__name__` variable will be set to `"__main__"` when executed
   - Use RUN_FILE:filename.ext command
3. You can also create executable scripts with proper shebangs

When the user asks to debug or fix code:
1. Analyze the code for errors
2. Provide corrected version using EDIT_FILE command
3. Explain what was wrong

IMPORTANT - TOOL EXECUTION ORDER:
The system executes tool operations strictly in the order they appear in your response. If you need multiple steps, list them in the exact order.
After tool execution, the system may auto-followup you with results unless you end your response with COMPLETE_TASK.

Always respond in a helpful, concise manner. Use code blocks for code, file operations for file changes.
Remember: Conversation history is preserved, so you can reference earlier messages!
"""
    
    return context

@app.route('/api/files', methods=['GET'])
def get_files():
    """Get all files"""
    try:
        if os.path.exists('data/files.json'):
            with open('data/files.json', 'r') as f:
                payload = json.load(f)
                if isinstance(payload, dict) and 'files' in payload:
                    return jsonify(payload)
                return jsonify({'files': payload, 'folders': [], 'folderState': {}})
    except:
        pass
    return jsonify({'files': {}, 'folders': [], 'folderState': {}})

@app.route('/api/files', methods=['POST'])
def save_files():
    """Save all files"""
    try:
        payload = request.json
        if isinstance(payload, dict) and 'files' in payload:
            data = {
                'files': payload.get('files', {}),
                'folders': payload.get('folders', []),
                'folderState': payload.get('folderState', {})
            }
        else:
            data = {
                'files': payload or {},
                'folders': [],
                'folderState': {}
            }
        with open('data/files.json', 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/execute', methods=['POST'])
def execute_code():
    """Execute code in a safe environment with comprehensive but secure module support"""
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python')
    
    if language == 'python':
        try:
            import io
            import sys
            import traceback
            
            # Redirect stdout to capture output
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            
            # Create string buffers for input/output
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            sys.stdout = output_buffer
            sys.stderr = error_buffer
            
            # Define allowed modules
            allowed_modules = [
                # Core libraries (generally safe)
                'datetime',
                'math',
                'json',
                're',
                'random',
                'time',
                'collections',
                'itertools',
                'functools',
                'operator',
                'string',
                'hashlib',
                'base64',
                'uuid',
                'os.path',  # Only the path module, not full os
                'pathlib',
                'statistics',
                'decimal',
                'fractions',
                'typing',
                'enum',
                'copy',
                'pprint',
                'textwrap',
                'csv',
                'html',
                'html.parser',
                'html.entities',
                'urllib.parse',
                
                # Safe numeric/scientific
                'numbers',
                'cmath',
                'bisect',
                'heapq',
                'array',
                
                # Data structures
                'queue',
                'collections.abc',
                
                # Text processing
                'unicodedata',
                'difflib',
                'codecs',
                
                # Safe system (limited)
                'sys',
                'platform',
                'errno',
                'getpass',  # Will return placeholder values
                
                # Testing/debugging
                'unittest.mock',  # For mocking in tests
                'doctest',
                
                # Date/time extended
                'calendar',
                'zoneinfo',
                
                # Limited file operations
                'io',
                'tempfile',
                
                # Safe internet (parsing only)
                'email',
                'email.parser',
                'email.message',
                
                # Compressed data (read-only)
                'gzip',
                'zipfile',  # Read-only mode only
                'tarfile',  # Read-only mode only
                
                # Configuration
                'configparser',
                
                # Logging (safe version)
                'logging',
            ]
            
            def safe_import(name, *args, **kwargs):
                """Safe import function that only allows whitelisted modules"""
                
                # Define submodules that are allowed
                allowed_submodules = {
                    'os': ['path'],
                    'collections': ['abc'],
                    'email': ['parser', 'message'],
                    'html': ['parser', 'entities'],
                    'urllib': ['parse'],
                    'unittest': ['mock'],
                    'zipfile': [],  # Will be restricted in usage
                    'tarfile': [],  # Will be restricted in usage
                }
                
                # Check if it's a direct allowed module
                if name in allowed_modules:
                    # Import the module safely
                    module = __import__(name, *args, **kwargs)
                    
                    # Apply restrictions for certain modules
                    if name == 'os':
                        # Create a safe os module with only path functions
                        safe_os = type('module', (), {})
                        # Copy only safe path functions
                        for attr in ['path']:
                            setattr(safe_os, attr, getattr(module, attr, None))
                        return safe_os
                        
                    elif name == 'sys':
                        # Create safe sys module
                        safe_sys = type('module', (), {
                            'argv': [''],
                            'version': module.version,
                            'version_info': module.version_info,
                            'platform': module.platform,
                            'maxsize': module.maxsize,
                            'stdout': module.stdout,
                            'stderr': module.stderr,
                            'stdin': module.stdin,
                            'exit': lambda code=0: None,  # Override exit
                            'modules': {},  # Empty modules dict
                            'path': [],  # Empty path
                        })
                        return safe_sys
                        
                    elif name == 'zipfile':
                        # Only allow reading, not writing
                        class SafeZipFile:
                            def __init__(self, file, mode='r', *args, **kwargs):
                                if mode not in ['r', 'rb']:
                                    raise ValueError("Only read mode is allowed")
                                self._zip = module.ZipFile(file, mode, *args, **kwargs)
                            
                            def __getattr__(self, name):
                                return getattr(self._zip, name)
                        
                        safe_zipfile = type('module', (), {
                            'ZipFile': SafeZipFile,
                            'is_zipfile': module.is_zipfile,
                        })
                        return safe_zipfile
                        
                    elif name == 'tarfile':
                        # Only allow reading, not writing
                        class SafeTarFile:
                            def __init__(self, name=None, mode='r', *args, **kwargs):
                                if mode not in ['r', 'r:']:
                                    raise ValueError("Only read mode is allowed")
                                self._tar = module.open(name, mode, *args, **kwargs)
                            
                            def __getattr__(self, name):
                                return getattr(self._tar, name)
                        
                        safe_tarfile = type('module', (), {
                            'open': lambda name, mode='r', *args, **kwargs: SafeTarFile(name, mode, *args, **kwargs),
                            'is_tarfile': module.is_tarfile,
                        })
                        return safe_tarfile
                        
                    elif name == 'getpass':
                        # Return placeholder values instead of real input
                        safe_getpass = type('module', (), {
                            'getpass': lambda prompt='Password: ': '********',
                            'getuser': lambda: 'user',
                        })
                        return safe_getpass
                        
                    elif name == 'logging':
                        # Create safe logging that doesn't write to files
                        safe_logging = type('module', (), {})
                        # Copy only basic functions
                        for attr in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL',
                                    'getLogger', 'basicConfig', 'Logger']:
                            if hasattr(module, attr):
                                setattr(safe_logging, attr, getattr(module, attr))
                        return safe_logging
                    
                    return module
                
                # Check if it's an allowed submodule (e.g., os.path)
                parts = name.split('.')
                if len(parts) > 1:
                    main_module = parts[0]
                    if main_module in allowed_submodules and parts[1] in allowed_submodules[main_module]:
                        # Import parent first
                        parent = __import__(main_module, *args, **kwargs)
                        # Return the specific submodule
                        for part in parts[1:]:
                            parent = getattr(parent, part)
                        return parent
                
                raise ImportError(f"Module '{name}' is not allowed in the safe execution environment")
            
            # Safe builtins with proper __import__
            safe_builtins = {
                '__name__': '__main__',  # This makes if __name__ == "__main__": work
                '__builtins__': {
                    'print': print,
                    'len': len,
                    'range': range,
                    'str': str,
                    'int': int,
                    'float': float,
                    'list': list,
                    'dict': dict,
                    'tuple': tuple,
                    'set': set,
                    'bool': bool,
                    'type': type,
                    'abs': abs,
                    'sum': sum,
                    'min': min,
                    'max': max,
                    'sorted': sorted,
                    'enumerate': enumerate,
                    'zip': zip,
                    'input': lambda prompt='': '',  # Return empty string for safety
                    'open': lambda *args, **kwargs: None,  # Disable file opening
                    '__import__': safe_import,  # Add safe import function
                    'isinstance': isinstance,
                    'issubclass': issubclass,
                    'hasattr': hasattr,
                    'getattr': getattr,
                    'setattr': setattr,
                    'delattr': delattr,
                    'property': property,
                    'staticmethod': staticmethod,
                    'classmethod': classmethod,
                    'super': super,
                    'repr': repr,
                    'ascii': ascii,
                    'format': format,
                    'vars': vars,
                    'dir': dir,
                    'id': id,
                    'hash': hash,
                    'hex': hex,
                    'oct': oct,
                    'bin': bin,
                    'chr': chr,
                    'ord': ord,
                    'pow': pow,
                    'round': round,
                    'divmod': divmod,
                    'all': all,
                    'any': any,
                    'callable': callable,
                    'filter': filter,
                    'map': map,
                    'next': next,
                    'iter': iter,
                    'slice': slice,
                    'memoryview': memoryview,
                    'object': object,
                    'NotImplemented': NotImplemented,
                    'Ellipsis': Ellipsis,
                }
            }
            
            # Pre-import safe modules for better performance
            safe_modules = {}
            for module_name in allowed_modules:
                try:
                    if '.' not in module_name:  # Skip submodules for now
                        safe_modules[module_name] = __import__(module_name)
                except ImportError:
                    pass  # Skip modules that aren't available
            
            # Also pre-import common submodules
            # submodules_to_preload = [
            #     'os.path',
            #     'collections.abc',
            #     'urllib.parse',
            #     'email.parser',
            #     'email.message',
            #     'html.parser',
            #     'html.entities',
            # ]
            
            # for submodule in submodules_to_preload:
            #     try:
            #         parts = submodule.split('.')
            #         module = __import__(parts[0])
            #         for part in parts[1:]:
            #             module = getattr(module, part)
            #         safe_modules[submodule] = module
            #     except ImportError:
            #         pass
            
            # Create execution namespace with pre-imported modules
            namespace = {
                '__name__': '__main__',
                '__builtins__': safe_builtins['__builtins__']
            }
            # Add the safe modules
            namespace.update(safe_modules)
            
            # Execute the code
            exec(code, namespace)
            
            # Get the output
            output = output_buffer.getvalue()
            error_output = error_buffer.getvalue()
            
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            # Combine output and error output
            full_output = output
            if error_output:
                full_output += "\nErrors:\n" + error_output
            
            return jsonify({
                'success': True,
                'output': full_output,
                'error': None
            })
        except Exception as e:
            # Restore stdout/stderr even on error
            if 'old_stdout' in locals():
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            return jsonify({
                'success': False,
                'output': '',
                'error': str(e),
                'traceback': traceback.format_exc()
            })
    else:
        return jsonify({
            'success': False,
            'error': f'Language {language} not supported yet'
        })

@app.route('/api/format', methods=['POST'])
def format_code():
    """Format code (simple implementation)"""
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python')
    
    # Simple formatting - in production, use proper formatters
    if language == 'python':
        try:
            import autopep8
            formatted = autopep8.fix_code(code)
            return jsonify({'success': True, 'formatted': formatted})
        except:
            # Fallback: just add proper indentation
            lines = code.split('\n')
            formatted_lines = []
            indent = 0
            for line in lines:
                stripped = line.strip()
                if stripped.endswith(':'):
                    formatted_lines.append(' ' * indent + line.lstrip())
                    indent += 4
                elif stripped and stripped[0] in ')]}':
                    indent = max(0, indent - 4)
                    formatted_lines.append(' ' * indent + line.lstrip())
                else:
                    formatted_lines.append(' ' * indent + line.lstrip())
            return jsonify({'success': True, 'formatted': '\n'.join(formatted_lines)})
    
    return jsonify({'success': True, 'formatted': code})

@app.route('/api/lint', methods=['POST'])
def lint_code():
    """Lint code"""
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python')
    
    issues = []
    
    if language == 'python':
        # Simple linting checks
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 80:
                issues.append({
                    'line': i,
                    'column': 80,
                    'severity': 'warning',
                    'message': 'Line too long (> 80 characters)'
                })
            if 'print ' in line:
                issues.append({
                    'line': i,
                    'column': line.find('print ') + 1,
                    'severity': 'info',
                    'message': 'Consider using logging instead of print for production code'
                })
            if 'TODO' in line or 'FIXME' in line:
                issues.append({
                    'line': i,
                    'column': 1,
                    'severity': 'info',
                    'message': 'TODO/FIXME comment found'
                })
    
    return jsonify({'issues': issues})

# ========== CONVERSATION THREAD API ==========

def load_threads():
    """Load threads from storage"""
    try:
        if os.path.exists(THREADS_FILE):
            with open(THREADS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_threads(threads):
    """Save threads to storage"""
    try:
        with open(THREADS_FILE, 'w') as f:
            json.dump(threads, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving threads: {e}")
        return False

@app.route('/api/threads', methods=['GET'])
def get_threads():
    """Get all conversation threads"""
    threads = load_threads()
    # Return threads without full message content (just metadata)
    thread_list = []
    for thread_id, thread_data in threads.items():
        thread_list.append({
            'id': thread_id,
            'title': thread_data.get('title', 'Untitled'),
            'created': thread_data.get('created'),
            'updated': thread_data.get('updated'),
            'message_count': len(thread_data.get('messages', []))
        })
    # Sort by updated date, newest first
    thread_list.sort(key=lambda x: x.get('updated', 0), reverse=True)
    return jsonify(thread_list)

@app.route('/api/threads/<thread_id>', methods=['GET'])
def get_thread(thread_id):
    """Get a specific thread with all messages"""
    threads = load_threads()
    if thread_id in threads:
        return jsonify(threads[thread_id])
    return jsonify({'error': 'Thread not found'}), 404

@app.route('/api/threads', methods=['POST'])
def create_thread():
    """Create a new conversation thread"""
    data = request.json or {}
    thread_id = str(uuid.uuid4())
    
    threads = load_threads()
    threads[thread_id] = {
        'id': thread_id,
        'title': data.get('title', 'New Conversation'),
        'created': int(datetime.now().timestamp() * 1000),
        'updated': int(datetime.now().timestamp() * 1000),
        'messages': []
    }
    
    if save_threads(threads):
        return jsonify(threads[thread_id])
    return jsonify({'error': 'Failed to create thread'}), 500

@app.route('/api/threads/<thread_id>', methods=['PUT'])
def update_thread(thread_id):
    """Update thread metadata (title)"""
    data = request.json
    threads = load_threads()
    
    if thread_id in threads:
        if data.get('title'):
            threads[thread_id]['title'] = data['title']
        threads[thread_id]['updated'] = int(datetime.now().timestamp() * 1000)
        
        if save_threads(threads):
            return jsonify(threads[thread_id])
    return jsonify({'error': 'Thread not found'}), 404

@app.route('/api/threads/<thread_id>/messages', methods=['POST'])
def add_message(thread_id):
    """Add a message to a thread"""
    data = request.json
    threads = load_threads()
    
    if thread_id in threads:
        message = {
            'role': data.get('role', 'user'),
            'content': data.get('content', ''),
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        threads[thread_id]['messages'].append(message)
        threads[thread_id]['updated'] = int(datetime.now().timestamp() * 1000)
        
        if save_threads(threads):
            return jsonify(message)
    return jsonify({'error': 'Thread not found'}), 404

@app.route('/api/threads/<thread_id>', methods=['DELETE'])
def delete_thread(thread_id):
    """Delete a conversation thread"""
    threads = load_threads()
    
    if thread_id in threads:
        del threads[thread_id]
        if save_threads(threads):
            return jsonify({'success': True})
    return jsonify({'error': 'Thread not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
