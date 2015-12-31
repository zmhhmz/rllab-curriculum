require 'pry'
require 'nokogiri'
require 'active_support/all'

def suicide
  Process.kill 9, Process.pid
end

class Array
  def _is_1d_vector?
    self.all?{|x| (x.is_a? Numeric) || (x.is_a? String) || (x.is_a? Symbol) }
  end

  def _is_2d_vector?
    self.any?{|x| x.try(:_is_1d_vector?) }
  end

  def to_s
    if _is_2d_vector?
      self.map(&:to_s).join(";")
    elsif _is_1d_vector?
      self.map(&:to_s).join(",")
    else
      super
    end
  end

  def sum
    reduce(:+)
  end

  def base_merge(other)
    zip(other).map(&:sum)
  end
end

def _compute_rect_vertices(from, to, radius)
  x1, y1 = from
  x2, y2 = to
  if (y1 - y2).abs < 1e-6
    dx = 0
    dy = radius
  else
    dx = radius * 1.0 / (((x1 - x2) / (y1 - y2)) ** 2 + 1) ** 0.5
    # equivalently dx = radius * (y2-y1).to_f / ((x2-x1)**2 + (y2-y1)**2)**0.5
    dy = (radius**2 - dx**2) ** 0.5
    dy *= (x1 - x2) * (y1 - y2) > 0 ? -1 : 1
  end
  [
    [x1 + dx, y1 + dy],
    [x2 + dx, y2 + dy],
    [x2 - dx, y2 - dy],
    [x1 - dx, y1 - dy],
  ]
end

class Nokogiri::XML::Builder

  alias_method :old_method_missing, :method_missing
  def method_missing(method, *args, &block)
    if @processors and (h = args[0]).is_a? Hash
      args[0] = @processors.reduce(h) { |accm, p| p.call(method, accm) }
    end
    old_method_missing(method, *args, &block)
  end

  def process(p, &block)
    @processors ||= []
    @processors << p
    instance_eval(&block)
    @processors.pop
  end

  def base(options={}, &block)
    p = Proc.new do |name, opts|
      if addon = options[name]
        addon.each do |k, v|
          if old_v = opts[k]
            opts = opts.merge({k => old_v.base_merge(v)})
          else
            opts = opts.merge({k => v})
          end
        end
      end
      opts
    end
    process(p, &block)
  end

  def query(prefix, key)
    if @processors
      @processors.reduce({}) { |accm, p| p.call(prefix, accm) }[key]
    end
  end

  def capsule(options={})
    from = options.delete(:from)
    to = options.delete(:to)
    radius = options.delete(:radius)
    vertices = _compute_rect_vertices(from, to, radius)
    fixture(options.merge(shape: :polygon, vertices: vertices))
    fixture(options.merge(shape: :circle, center: from, radius: radius))
    fixture(options.merge(shape: :circle, center: to, radius: radius))
  end

  def rect(options={})
    from = options.delete(:from)
    to = options.delete(:to)
    radius = options.delete(:radius)
    box = options.delete(:box)
    if from and to and radius
      vertices = _compute_rect_vertices(from, to, radius)
      fixture(options.merge(shape: :polygon, vertices: vertices))
    elsif box
      fixture(options.merge(shape: :polygon, box: box))
    else
      raise 'what?'
    end
  end

end

class Numeric

  def deg
    self
  end

  def to_rad
    self * 1.0 / 180 * Math::PI
  end

  def N
    self
  end

  def Nm
    self
  end

  def base_merge(other)
    self + other
  end

end

builder = Nokogiri::XML::Builder.new do
  eval(open(ARGV.first).read)
end
puts "<!-- Auto-generated. Do not edit! -->"
puts builder.doc.root.to_s
