# VideoDownloader
支持自动m3u8爬取、密钥爬取、断点续传及文件清理的Python小爬虫

- 适用站点：直接使用m3u8文件进行stream ts file下载，并经AES-CBC-128加密的视频网站（比如jable.tv）
- BeautifulSoup寻找m3u8文件路径并下载
- 解析m3u8文件获取密钥路径与初始向量（IV）
- 多线程同时下载
- clear()与merge_ts()函数分别负责清理文件夹下的空ts文件（下载失败但已打开文件流）和合并ts文件

> 记得修改site_url为要爬取的网页视频链接 :P

- 若要转换为mp4格式，直接使用命令：
  `ffmpeg -i final.ts -c copy -bsf:a aac_adtstoasc final.mp4`
- 有问题欢迎直接linxzhan9@gmail.com
