function y = ImgQuantile(img, p)
    [Nr,Nc,Nk] = size(img);
    y = zeros(Nk,numel(p));
    %NK=3,numel(p)=2
    for index = 1:Nk
        y(index,:) = quantile(img(:,:,index), p);
    end 
end

function y = quantile(x, p)
    x = sort(x(:));
    p = max(floor(numel(x)*p),1);
    y = x(p);
    

end