using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace ValkyrieFS.Service;

public static class Program
{
    public static void Main(string[] args)
    {
        var builder = Host.CreateApplicationBuilder(args);

        // Windows Service로 실행될 수 있게 설정
        builder.Services.AddWindowsService(options =>
        {
            options.ServiceName = "ValkyrieFS Service";
        });

        builder.Logging.ClearProviders();
        builder.Logging.AddConsole(); // 개발/디버깅용
        builder.Logging.AddEventLog(); // 운영(서비스) 로그

        builder.Services.AddHostedService<Worker>();

        var host = builder.Build();
        host.Run();
    }
}


