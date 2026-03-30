"""``aura ai "<prompt>"`` command handler."""

from aura_os.ai.inference import LocalInference
from aura_os.ai.model_manager import ModelManager
from aura_os.shell.colors import cyan, dim, green, red


class AiCommand:
    """Query a local AI model with a text prompt.

    Tries runtimes in order: ollama → llama-cli → instructional fallback.
    """

    def execute(self, args, eal) -> int:
        """Run the AI query and print the result.

        Returns 0 on success, 1 if an error occurred.
        """
        prompt = args.prompt
        model = getattr(args, "model", None)
        max_tokens = getattr(args, "max_tokens", 512)

        mm = ModelManager()
        inference = LocalInference(model_manager=mm)

        print(f"  {cyan('[aura ai]')} {dim('Querying local AI…')}\n")
        try:
            response = inference.query(prompt, model=model, max_tokens=max_tokens)
            print(f"  {green('❯')} {response}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"  {red('[aura ai]')} Unexpected error: {exc}")
            return 1
