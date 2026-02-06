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
    files_list = []
    
    try:
        # Check if we have a data directory
        if os.path.exists('data'):
            if os.path.exists('data/files.json'):
                with open('data/files.json', 'r') as f:
                    files_data = json.load(f)
                    files_list = list(files_data.values())
    except:
        pass
    
    # Default files if none exist
    if not files_list:
        files_list = [
            {
                'id': 'default_1',
                'name': 'README.md',
                'content': '# Welcome to Kimi Workspace\n\nThis is an AI-powered coding environment.\n\n## Features:\n- 🤖 AI-assisted coding with Kimi K2\n- 📁 File management\n- 📝 Multi-tab editor\n- 💬 Integrated chat\n- 🔧 Server-side processing\n- 🛠️ Advanced tools\n\nTry asking Kimi to create files for you!',
                'language': 'markdown',
                'saved': True,
                'lastModified': int(datetime.now().timestamp() * 1000)
            }
        ]
    
    # Build the system context/prompt server-side
    system_context = build_system_context(files_list)

    # Escape for JavaScript - replace backticks with a placeholder
    escaped_context = system_context.replace('`', 'BACKTICK_PLACEHOLDER')

    # Render template
    return render_template('index.html', 
                        initial_files=json.dumps(files_list),
                        server_url=request.host_url,
                        version='1.1.0',
                        system_context=escaped_context)


def build_system_context(files_list):
    """Build the AI system context/prompt server-side"""
    context = """CRITICAL: You are operating inside the "Kimi Workspace," a specialized IDE environment. 
Unlike a standard chat, YOU HAVE DIRECT ACCESS to the user's filesystem through specific command tags. 
You MUST use these tags to perform actions. Do not say you cannot manage files.

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

3. To request to see a file's content: READ_FILE:filename.ext

4. To run/execute a Python file: RUN_FILE:filename.ext
   - When running Python files, the code will be executed in a safe environment
   - Code inside `if __name__ == "__main__":` blocks WILL execute when the file is run
   - This is the correct behavior - use this pattern for standalone scripts
   - Functions and classes defined at module level will be available

5. To analyze/lint a file: LINT_FILE:filename.ext

CONVERSATION THREADS:
- The workspace maintains conversation history per thread
- Each conversation remembers its past messages
- You should reference previous context when relevant
- Thread history persists across page refreshes
- Users can create new threads for separate conversations

Current Files in Workspace:
"""
    
    if not files_list:
        context += "- (The workspace is currently empty)\n"
    else:
        for file in files_list:
            context += f"- {file['name']} ({file.get('language', 'unknown')})\n"
    
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
                return jsonify(json.load(f))
    except:
        pass
    return jsonify({})

@app.route('/api/files', methods=['POST'])
def save_files():
    """Save all files"""
    try:
        files = request.json
        with open('data/files.json', 'w') as f:
            json.dump(files, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/execute', methods=['POST'])
def execute_code():
    """Execute code in a safe environment"""
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python')
    
    # IMPORTANT: In production, use proper sandboxing!
    # This is a simple example for demo purposes
    
    if language == 'python':
        try:
            # Create a safe execution environment
            import io
            import sys
            import traceback
            
            # Redirect stdout to capture output
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            # Safe builtins
            safe_builtins = {
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
                'zip': zip
            }
            
            # Execute the code
            exec(code, {'__builtins__': safe_builtins})
            
            # Get the output
            output = sys.stdout.getvalue()
            
            # Restore stdout
            sys.stdout = old_stdout
            
            return jsonify({
                'success': True,
                'output': output,
                'error': None
            })
        except Exception as e:
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
    # print("🚀 Kimi Workspace Server v1.1")
    # print("🌐 http://localhost:5000")
    # print("✨ Features:")
    # print("  - AI File Creation")
    # print("  - Multi-Tab Editor")
    # print("  - GitHub-Style UI")
    # print("  - Server-Side Processing")
    # print("  - Code Execution API")
    # print("  - Formatting & Linting")
    # print("  - File Persistence")
    app.run(host='0.0.0.0', port=5000, debug=True)