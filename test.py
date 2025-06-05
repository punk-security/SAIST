import asyncio
import os
import sys
sys.path.append('saist')

# Set environment variables
os.environ['ANTHROPIC_API_KEY'] = 'your-api-key-here'
os.environ['SAIST_LLM_API_KEY'] = 'your-api-key-here'

async def debug_llm_adapter():
    try:
        # Import the function
        from saist.main import _get_llm_adapter
        
        # Create args with debug info
        class Args:
            llm = 'anthropic'
            llm_api_key = 'your-api-key-here'
            llm_model = None
            
        args = Args()
        
        # Print what we're passing in
        print("Args.llm:", args.llm)
        print("Args.llm_api_key:", args.llm_api_key)
        print("Args.llm_model:", args.llm_model)
        print("Environment ANTHROPIC_API_KEY:", os.environ.get('ANTHROPIC_API_KEY', 'NOT SET'))
        print("Environment SAIST_LLM_API_KEY:", os.environ.get('SAIST_LLM_API_KEY', 'NOT SET'))
        
        # Try to call it
        adapter = await _get_llm_adapter(args)
        print("Success! LLM adapter created:", adapter)
        
    except Exception as e:
        print("Error creating LLM adapter:", e)
        
        # Let's try to examine the source code of the function
        import inspect
        from saist.main import _get_llm_adapter
        print("\nFunction source code:")
        print(inspect.getsource(_get_llm_adapter))

asyncio.run(debug_llm_adapter())