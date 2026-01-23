using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace ValkyrieFS.Service;

// NOTE: 여기서는 "서비스 + IPC" 뼈대만 제공합니다.
// 실제 인덱싱/검색 코어(C++) 연동은 다음 단계에서 붙입니다.
public sealed class Worker : BackgroundService
{
    private readonly ILogger<Worker> _logger;

    // Everything 스타일: 로컬 전용 Named Pipe
    private const string PipeName = "ValkyrieFS.Pipe";

    public Worker(ILogger<Worker> logger)
    {
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("ValkyrieFS Service started.");

        // 단일 파이프 서버를 반복적으로 accept (간단/안정 우선)
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                using var server = new NamedPipeServerStream(
                    PipeName,
                    PipeDirection.InOut,
                    maxNumberOfServerInstances: 1,
                    PipeTransmissionMode.Message,
                    PipeOptions.Asynchronous);

                _logger.LogInformation("Waiting for UI connection on pipe {PipeName}", PipeName);
                await server.WaitForConnectionAsync(stoppingToken);
                _logger.LogInformation("UI connected.");

                await HandleClientAsync(server, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Service loop error");
                // 과도한 재시작 루프 방지
                await Task.Delay(300, stoppingToken);
            }
        }

        _logger.LogInformation("ValkyrieFS Service stopping.");
    }

    private async Task HandleClientAsync(NamedPipeServerStream pipe, CancellationToken ct)
    {
        // JSON Lines 프로토콜(한 줄 = 한 메시지)
        using var reader = new StreamReader(pipe, Encoding.UTF8, detectEncodingFromByteOrderMarks: false, bufferSize: 64 * 1024, leaveOpen: true);
        using var writer = new StreamWriter(pipe, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false), bufferSize: 64 * 1024, leaveOpen: true)
        {
            AutoFlush = true
        };

        while (pipe.IsConnected && !ct.IsCancellationRequested)
        {
            string? line;
            try
            {
                line = await reader.ReadLineAsync(ct);
            }
            catch (OperationCanceledException)
            {
                break;
            }

            if (line == null) break;
            if (string.IsNullOrWhiteSpace(line)) continue;

            try
            {
                using var doc = JsonDocument.Parse(line);
                var root = doc.RootElement;
                var type = root.TryGetProperty("type", out var t) ? t.GetString() : null;

                switch (type)
                {
                    case "ping":
                        await writer.WriteLineAsync("{\"type\":\"pong\"}");
                        break;

                    case "status":
                        // TODO: 인덱싱 상태/파일 수/메모리/마지막 USN 등으로 확장
                        await writer.WriteLineAsync("{\"type\":\"status\",\"ready\":true}");
                        break;

                    case "search":
                        // TODO: C++ 메모리 인덱스에 직접 연결(P/Invoke) 또는 별도 엔진으로 위임
                        await writer.WriteLineAsync("{\"type\":\"search_result\",\"results\":[]}");
                        break;

                    default:
                        await writer.WriteLineAsync("{\"type\":\"error\",\"message\":\"unknown_request\"}");
                        break;
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Bad request");
                await writer.WriteLineAsync("{\"type\":\"error\",\"message\":\"bad_request\"}");
            }
        }
    }
}


