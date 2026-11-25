ObjC.import('PDFKit');
function run(argv){const d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));let o=[];for(let i=0;i<d.pageCount;i++)o.push('=== PAGE '+(i+1)+' ===\n'+d.pageAtIndex(i).string.js);return o.join('\n');}
