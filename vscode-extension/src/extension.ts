import * as vscode from "vscode";
import { Executable, LanguageClient, LanguageClientOptions } from "vscode-languageclient/node";

let client: LanguageClient | undefined;

export function activate(context: vscode.ExtensionContext): void {
    const config = vscode.workspace.getConfiguration("pytestLinter");

    if (!config.get<boolean>("enable", true)) {
        return;
    }

    const serverPath = config.get<string>("path", "pytest-linter-lsp");

    const serverOptions: Executable = {
        command: serverPath,
        args: [],
    };

    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: "file", language: "python" }],
    };

    client = new LanguageClient("pytest-linter", "pytest-linter", serverOptions, clientOptions);

    context.subscriptions.push(client.start());
}

export function deactivate(): Thenable<void> | undefined {
    return client?.stop();
}
